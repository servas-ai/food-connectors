"""SPAR/INTERSPAR Österreich — live connector via SPAR's public product search API.

Access path (no login, no cookies, no browser, no Cloudflare page touched):
  https://search-spar.spar-ics.com/fact-finder/rest/v4/search/products_lmos_at?query=...&q=...&page=1&hitsPerPage=N
This is the JSON search index the interspar.at shop front-end queries (the same endpoint heisse-preise.io
uses, badlogic/heissepreise MIT). The host has no robots.txt (404 → no restrictions); interspar.at HTML itself
sits behind Cloudflare and is never requested here.
An article number (interspar.at/p/<id>) as query returns exactly that article (articleNumberSearch=true) with
current shelf price, regular price, price per unit, SPAR internal code (code-internal — 88… prefix, NOT a GTIN, so never mapped to ean), brand, category path, stock status and
the public CDN image. totalHits=0 for an article number = not listed in the online assortment any more.
"""
from __future__ import annotations
import re, time, urllib.parse
from ..http import get
from ..schema import Product
from .base import Adapter

API = "https://search-spar.spar-ics.com/fact-finder/rest/v4/search/products_lmos_at"
SHOP = "https://www.interspar.at/shop/lebensmittel"
MEAL_CATS = ("Fertiggerichte", "Suppen", "Tiefkühl-Fertiggerichte", "Pizza", "Feinkost")

def _q(query: str, n: int = 24, page: int = 1) -> dict:
    qs = urllib.parse.urlencode({"query": query, "q": query, "page": page, "hitsPerPage": n})
    return get(f"{API}?{qs}", timeout=30)

def _size(s: str | None):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(G|KG|ML|L)\b", (s or "").upper())
    if not m: return None
    v = float(m.group(1).replace(",", ".")); return round(v * 1000) if m.group(2) in ("KG", "L") else round(v)

def _ppu(s: str | None):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*€/(kg|l|Stk)", s or "", re.I)
    return (float(m.group(1).replace(",", ".")), m.group(2).lower()) if m else (None, None)

def to_product(hit: dict) -> Product:
    mv = hit.get("masterValues") or {}
    ppu, unit = _ppu(mv.get("price-per-unit"))
    brand = mv.get("ecr-brand") or ((mv.get("brand") or [None])[0])
    url = mv.get("url") or ""
    return Product(source="spar-shop", store="SPAR/INTERSPAR", name=f"{brand or ''} {mv.get('short-description-2') or mv.get('short-description') or ''}".strip(),
        brand=brand, price_eur=mv.get("price"), unit_price_eur=ppu, unit=unit, size_g=_size(mv.get("short-description-3")),
        ean=None, image_url=mv.get("image-url"), category=mv.get("category-names"),
        source_url=(SHOP + url) if url.startswith("/") else url or None, source_id=str(mv.get("product-number") or hit.get("id")),
        extra={"regular_price_eur": mv.get("regular-price"), "best_price_eur": mv.get("best-price"), "on_promotion": mv.get("is-on-promotion") == "true",
               "stock_status": mv.get("stock-status"), "spar_code_internal": mv.get("code-internal"), "item_type": mv.get("item-type"), "sales_unit": mv.get("sales-unit"),
               "price_basis": "per 100 g (counter/weight product; best_price = €/kg)" if mv.get("item-type") == "WeightProduct" else "per pack", "pack": mv.get("short-description-3"), "bio": mv.get("biolevel"),
               "allergens_declared": mv.get("customer-general-info-name"), "api": API})

def article(article_id: str | int) -> Product | None:
    """Exact lookup by SPAR article number; None if the article is not (any more) in the online assortment."""
    d = _q(str(article_id), n=3)
    for h in d.get("hits") or []:
        if str((h.get("masterValues") or {}).get("product-number")) == str(article_id):
            return to_product(h)
    return None

def is_ready_meal(p: Product) -> bool:
    c = p.category or ""
    return "Fertiggerichte" in c or "Suppen" in c

class SparShop(Adapter):
    id = "spar-shop"; store = "SPAR/INTERSPAR"; homepage = "https://www.interspar.at"; status = "live"
    notes = ("Live: SPAR public product search API (search-spar.spar-ics.com fact-finder, no robots.txt, no login/cookies) — "
             "current + regular price, €/kg, SPAR-internal code (not a GTIN), brand, category, stock status, CDN image; exact lookup by article number "
             "(interspar.at/p/<id>). interspar.at HTML (Cloudflare) is never requested. No nutrition in this index.")
    delay = 0.4
    def search(self, q: str, limit: int = 20) -> list[Product]:
        d = _q(q, n=min(max(limit, 1), 100))
        return [to_product(h) for h in (d.get("hits") or [])][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 200) -> list[Product]:
        if category != "ready-meals": return self.search(category, limit)
        out, seen = [], set()
        for term in ("Fertiggericht", "Eintopf", "Gulasch", "Suppe", "Lasagne", "Risotto", "Curry"):
            for page in (1, 2):
                try: d = _q(term, n=50, page=page)
                except Exception: break
                finally: time.sleep(self.delay)
                for h in d.get("hits") or []:
                    p = to_product(h)
                    if p.source_id in seen or not is_ready_meal(p): continue
                    seen.add(p.source_id); out.append(p)
                if len(out) >= limit: return out[:limit]
        return out[:limit]
