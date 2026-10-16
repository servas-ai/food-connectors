"""Open Prices (Open Food Facts) — crowd-sourced, proof-backed shelf prices by EAN.

Public REST API https://prices.openfoodfacts.org/api/v1/prices (no key, no login; ODbL 1.0).
Every observation carries a date, a currency, an OSM-located shop and a proof type
(RECEIPT / PRICE_TAG / GDPR_REQUEST / SHOP_IMPORT). These are user contributions, not
retailer feeds: label them 'crowd-sourced' and never treat them as a current shelf price
without checking date + country + shop.
"""
import time
import urllib.parse as up
from .http import get

API = "https://prices.openfoodfacts.org/api/v1/prices"
LICENCE = "ODbL 1.0 — Open Prices by Open Food Facts contributors"


def _row(p):
    loc = p.get("location") or {}
    prod = p.get("product") or {}
    return {
        "ean": p.get("product_code") or prod.get("code"),
        "price": p.get("price"),
        "price_without_discount": p.get("price_without_discount"),
        "discounted": bool(p.get("price_is_discounted")),
        "currency": p.get("currency"),
        "price_per": p.get("price_per"),
        "date": p.get("date"),
        "shop": loc.get("osm_name"),
        "shop_brand": loc.get("osm_brand"),
        "city": loc.get("osm_address_city"),
        "country": loc.get("osm_address_country_code"),
        "osm": f"{loc.get('osm_type', '').lower()}/{loc.get('osm_id')}" if loc.get("osm_id") else None,
        "proof_type": (p.get("proof") or {}).get("type"),
        "product_name": prod.get("product_name"),
        "source_url": f"https://prices.openfoodfacts.org/products/{p.get('product_code') or prod.get('code')}",
        "open_prices_id": p.get("id"),
    }


def parse(payload, country=None, since=None):
    rows = [_row(p) for p in (payload or {}).get("items", [])]
    if country:
        rows = [r for r in rows if (r["country"] or "").upper() == country.upper()]
    if since:
        rows = [r for r in rows if (r["date"] or "") >= since]
    rows.sort(key=lambda r: r["date"] or "", reverse=True)
    return rows


def prices(ean, country=None, since=None, size=100):
    """All Open Prices observations for one EAN (newest first), optionally filtered by
    ISO country code of the shop (e.g. 'AT') and minimum date (YYYY-MM-DD)."""
    q = up.urlencode({"product_code": str(ean).strip(), "size": size, "order_by": "-date"})
    return {"ean": str(ean).strip(), "licence": LICENCE, "observations": parse(get(f"{API}?{q}", timeout=40), country, since)}


def latest(eans, country="AT", since=None, delay=0.8):
    """Newest observation per EAN (polite, sequential). Returns {ean: row|None}."""
    out = {}
    for e in eans:
        try:
            obs = prices(e, country, since)["observations"]
            out[e] = obs[0] if obs else None
        except Exception as ex:
            out[e] = {"error": repr(ex)[:200]}
        time.sleep(delay)
    return out
