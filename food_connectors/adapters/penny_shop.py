"""PENNY Österreich — live connector for the public penny.at online-assortment JSON (REWE product-discovery API).

Access path (no login, no cookies, no browser):
  listing  https://www.penny.at/api/product-discovery/products?page=<n>&pageSize=100   (≈450 items, 5 pages)
  detail   https://www.penny.at/api/product-discovery/products/<sku>                   (sku = 78-<REWE article no.>)
These are the JSON calls the penny.at web shop itself makes. robots.txt (2026-10-13) contains only a Sitemap line
→ no Disallow. heisse-preise (badlogic/heissepreise, MIT) used the older /api/products path (disabled there since
14.10.2025); the product-discovery path is the current one (same API family as BILLA, see `billa`).
Per item: name, brand, pack (amount + volumeLabel), regular shelf price (price.regular, may carry a promotion such as
'ab 12 Packungen'), standard price (price.standard), €/unit, promotion validity, category path(s), country of origin,
official image (images.cdn.europe-west1.gcp.commercetools.com). Penny publishes NO GTIN and NO nutrition: use the
identical REWE article at BILLA (`billa` 00-<same no.>) or `off` by EAN for that. Only the online assortment
(~450 items incl. weekly offers) is listed — not the full store range.
"""
from __future__ import annotations
import re, time
from ..http import get
from ..schema import Product, parse_size_g
from .base import Adapter

BASE = "https://www.penny.at"
API = BASE + "/api/product-discovery/products"
MEAL_CATS = ("Tiefkühl > Fertiggerichte", "Grundnahrungsmittel > Fertiggerichte", "Kühlwaren > Schnelle Küche",
             "Tiefkühl > Pizza", "Tiefkühl > Fisch", "Asia Produkte", "Konserven")
MEAL_WORDS = ("gulasch", "lasagne", "schnitzel", "knödel", "pizza", "nudeln", "suppe", "eintopf", "curry", "risotto",
              "frühlingsrollen", "nuggets", "fischstäbchen", "backfisch", "goldschatz", "garnelen", "baked beans", "cevapcici",
              "spätzle", "gnocchi", "ravioli", "tortellini", "chili")
NOT_MEAL = re.compile(r"würze|brühe|bouillon|teigwaren|sauerkraut|aufstrich|thunfisch|sardinen|mais\b|paprika|frühstücksfleisch|pommes|kroketten", re.I)

def paths(r: dict) -> list[str]:
    return [" > ".join(c.get("name", "") for c in pc) for pc in (r.get("parentCategories") or []) if pc and "ngebot" not in pc[0].get("name", "")]

def to_product(r: dict) -> Product:
    pr = r.get("price") or {}; reg = pr.get("regular") or {}; std = pr.get("standard") or {}
    v = reg.get("value"); ppu = reg.get("perStandardizedQuantity"); sv = std.get("value")
    brand = (r.get("brand") or {}).get("name")
    pack = f"{r.get('amount', '')} {r.get('volumeLabelShort', '')}".strip()
    return Product(source="penny-shop", store="PENNY", name=(r.get("name") or "").strip(), brand=brand,
        price_eur=v / 100 if v else None, unit_price_eur=ppu / 100 if ppu else None, unit=pr.get("baseUnitShort"),
        size_g=parse_size_g(pack), ean=None, image_url=(r.get("images") or [None])[0],
        category=" | ".join(paths(r)) or r.get("category"),
        source_url=f"{BASE}/produkte/{r.get('slug')}" if r.get("slug") else None, source_id=r.get("sku"),
        extra={"standard_price_eur": sv / 100 if sv else None, "in_promotion": bool(r.get("inPromotion")),
               "promotion_text": reg.get("promotionText") or None, "promotion_type": reg.get("promotionType"),
               "valid_from": pr.get("validityStart"), "valid_to": pr.get("validityEnd"), "pack": pack,
               "variants": r.get("descriptionShort") or None, "origin": r.get("countryOfOrigin") or None,
               "weight_article": r.get("weightArticle") if "weightArticle" in r else r.get("isWeightArticle"),
               "rewe_article": (r.get("sku") or "").split("-")[-1] or None,
               "price_basis": "price_eur = price.regular (Regalpreis, may be a multi-buy promo price, see promotion_text); standard_price_eur = Normalpreis",
               "api": API})

def listing(pages: int = 10, delay: float = 1.0) -> list[dict]:
    out = []
    for page in range(pages):
        d = get(f"{API}?page={page}&pageSize=100", timeout=30)
        rs = d.get("results") or []; out += rs
        if len(rs) < 100 or len(out) >= (d.get("total") or 0): break
        time.sleep(delay)
    return out

def product(sku: str) -> Product | None:
    """Exact lookup by Penny sku ('78-785625' or bare REWE article number '785625'); None if not listed."""
    sku = sku if "-" in str(sku) else f"78-{sku}"
    try: d = get(f"{API}/{sku}", timeout=30)
    except Exception as e:
        if getattr(e, "code", None) == 404: return None
        raise
    return to_product(d) if d and d.get("sku") else None

def is_ready_meal(p: Product) -> bool:
    t = (p.name or "").lower(); c = p.category or ""
    if NOT_MEAL.search(t): return False
    return any(w in t for w in MEAL_WORDS) or any(m in c for m in MEAL_CATS[:3])

class PennyShop(Adapter):
    id = "penny-shop"; store = "PENNY"; homepage = BASE; status = "live"
    notes = ("Live: penny.at public online-assortment JSON (REWE product-discovery API, robots: Sitemap only, no login/cookies) — "
             "≈450 items: regular + standard price, promo text/validity, €/unit, pack, category path, origin, official image; "
             "exact lookup by sku 78-<REWE no.>. No GTIN/nutrition → identical BILLA article 00-<no.> or `off`.")
    def search(self, q: str, limit: int = 20) -> list[Product]:
        words = re.findall(r"\w{3,}", q.lower())
        ps = [to_product(r) for r in listing()]
        return [p for p in ps if all(w in f"{p.name} {p.brand or ''} {p.category or ''}".lower() for w in words)][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 500) -> list[Product]:
        ps = [to_product(r) for r in listing()]
        if category == "ready-meals": ps = [p for p in ps if is_ready_meal(p)]
        elif category != "all": ps = [p for p in ps if category.lower() in f"{p.name} {p.category or ''}".lower()]
        return ps[:limit]
