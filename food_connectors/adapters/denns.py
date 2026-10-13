"""denn's BioMarkt Österreich — live connector for the public weekly offer feed (Angebote).

Access path (no login, no cookies, no browser): the Gatsby page-data JSON that denns-biomarkt.at itself loads
  https://www.denns-biomarkt.at/page-data/angebote/page-data.json
robots.txt (denns-biomarkt.at / biomarkt.de): 'User-agent: * Allow: /' (checked 2026-10-13).
result.data.sanityAllOffers.nodes + noLimitOffers.nodes = current AT offers (land=at) with denn's article number
(itemno), brand, title, pack (subtitle, may be a range for multi-variant offers), offer price (price), regular shelf
price (priceb), unit price text (pricec), validity, vegan/vegetarian flags and the official product image
(images.dennree.de/fitinto/576x384/<itemno>.top.png). Only promo offers (~80/week) — not the full assortment,
no GTIN, no nutrition. Use `off` (Open Food Facts, stores tag denn-s-biomarkt) for nutrition.
"""
from __future__ import annotations
import re
from ..http import get
from ..schema import Product
from .base import Adapter

FEED = "https://www.denns-biomarkt.at/page-data/angebote/page-data.json"
PAGE = "https://www.denns-biomarkt.at/angebote/"
MEAL_WORDS = ("suppe", "eintopf", "gulasch", "fertig", "fingerfood", "nuggets", "pizza", "lasagne", "curry", "risotto",
              "knödel", "strudel", "pudding", "dessert", "maultasche", "bowl", "falafel", "antipasti", "chili")

def _eur(s):
    if s in (None, ""): return None
    m = re.search(r"\d+(?:,\d+)?", str(s)); return float(m.group(0).replace(",", ".")) if m else None

def _size(s):
    """Single pack size in g/ml; None for ranges/variants ('350 g / 380 g', '185 g - 200 g') or pieces."""
    s = (s or "").replace("je ", "").strip()
    m = re.fullmatch(r"(\d+(?:,\d+)?)\s*(g|kg|ml|l)", s, re.I)
    if not m: return None
    v = float(m.group(1).replace(",", ".")); return round(v * 1000) if m.group(2).lower() in ("kg", "l") else round(v)

def _ppu(s):
    m = re.match(r"\s*1\s*(kg|l)\s*=\s*(\d+(?:,\d+)?)\s*$", s or "", re.I)
    return (float(m.group(2).replace(",", ".")), m.group(1).lower()) if m else (None, None)

def offers(raw: dict | None = None) -> list[dict]:
    d = (raw or get(FEED, timeout=30))["result"]["data"]
    out, seen = [], set()
    for k in ("sanityAllOffers", "noLimitOffers"):
        for n in (d.get(k) or {}).get("nodes") or []:
            key = n.get("_id") or (n.get("itemno"), n.get("title"))
            if key in seen or n.get("land") != "at" or n.get("hidden"): continue
            seen.add(key); out.append(n)
    return out

def to_product(n: dict) -> Product:
    ppu, unit = _ppu(n.get("pricec"))
    img = (n.get("image") or "").split("?")[0] or None
    brand = (n.get("brand") or "").strip() or None
    title = (n.get("title") or "").replace("❄", "").strip()
    pg = ((n.get("articleGroup") or {}).get("productGroup") or {}).get("title")
    offer, regular = _eur(n.get("price")), _eur(n.get("priceb"))
    return Product(source="denns", store="denn's BioMarkt", name=f"{brand or ''} {title}".strip(), brand=brand,
        price_eur=offer, unit_price_eur=ppu, unit=unit, size_g=_size(n.get("subtitle")), ean=None, image_url=img,
        category=pg, source_url=PAGE, source_id=n.get("itemno"),
        extra={"offer_price_eur": offer, "regular_price_eur": regular, "unit_price_text": n.get("pricec"), "pack": n.get("subtitle"),
               "valid_from": n.get("validfrom"), "valid_to": n.get("validto"), "app_price_eur": _eur(n.get("priceApp")),
               "frozen": "❄" in (n.get("title") or ""), "vegan": n.get("vegan"), "vegetarian": n.get("vegetarian"),
               "lactosefree": n.get("lactosefree"), "glutenfree": n.get("glutenfree"), "offer_type": n.get("angebotsart"),
               "price_from": bool(n.get("priceAb")), "markets_n": len(set((n.get("marketIdList") or {}).get("marketIds") or [])),
               "price_basis": "Aktionspreis (offer) in price_eur; regular_price_eur = Normalpreis", "feed": FEED})

def is_ready_meal(p: Product) -> bool:
    t = (p.name or "").lower()
    return any(w in t for w in MEAL_WORDS)

class Denns(Adapter):
    id = "denns"; store = "denn's BioMarkt"; homepage = "https://www.denns-biomarkt.at"; status = "live"
    notes = ("Live: denn's BioMarkt AT weekly offers via the public Gatsby page-data JSON (robots Allow: /, no login/cookies): "
             "denn's article no., brand, pack, offer + regular price, €/kg, validity, vegan flags, official image (images.dennree.de). "
             "Offers only (~80/week), no GTIN/nutrition — combine with `off` (stores tag denn-s-biomarkt).")
    def search(self, q: str, limit: int = 20) -> list[Product]:
        ql = q.lower(); ps = [to_product(n) for n in offers()]
        return [p for p in ps if ql in f"{p.name} {p.category or ''}".lower()][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 200) -> list[Product]:
        ps = [to_product(n) for n in offers()]
        if category == "ready-meals": ps = [p for p in ps if is_ready_meal(p)]
        elif category != "all": ps = [p for p in ps if category.lower() in f"{p.name} {p.category or ''}".lower()]
        return ps[:limit]
