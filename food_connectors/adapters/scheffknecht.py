"""Ariane Scheffknecht (ariane-scheffknecht.at) — hand-made, pasteurised ready meals in jars from Lustenau,
Vorarlberg ('Convenience Food muss kein Junkfood sein'), sold in the own Wix webshop and in Vorarlberg
Sutterlüty/SPAR stores.

Source (public, no login/cookies; robots.txt ``User-agent: *`` ``Allow: /`` — only ``*?lightbox=`` disallowed):
  * ``https://www.ariane-scheffknecht.at/store-products-sitemap.xml`` — all product-page URLs (1 request);
  * each ``/product-page/<slug>`` page's server-rendered schema.org ``Product`` JSON-LD: name, price
    (EUR incl. USt), availability, images and a description with 'Zutaten: …' and 'NNNg, N Portionen'.
Wix has no public product JSON without the internal storefront API, which is never used → HTML/JSON-LD,
1 s per request (polite gate). Ready meals = all products minus 'Ragù alla Bolognese' (slug sugo-bolognese,
a pasta sauce). 'Gerstensuppe mit Käferbohnen' has no description (no size/ingredients published).
No nutrition and no GTIN are published → never estimated.
Shipping: products say 'zzgl. Versand', homepage 'Ab 12 Gläser versandkostenfrei'; the shipping fee itself is
not published on the static pages (2026-10-25) → left empty.
Operator (Impressum ariane-scheffknecht.at/datenschutz): Ariane Scheffknecht, Lorettoweg 14, A-6890 Lustenau,
office@ariane-scheffknecht.at; sole trader (Creditreform via firmenabc: Ariane Maria Scheffknecht, retail of
food since 16.03.2017); no UID and no Firmenbuch number published → VIES not checkable; GLEIF: no LEI.
"""
from __future__ import annotations
import html as _html, json, re
from urllib.parse import quote, unquote
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.ariane-scheffknecht.at"
STORE = "Online: Ariane Scheffknecht"
PRODUCER = "Ariane Scheffknecht, Lorettoweg 14, 6890 Lustenau, Vorarlberg"
SHIPPING_NOTE = "zzgl. Versand (Betrag nicht veröffentlicht); ab 12 Gläsern versandkostenfrei lt. ariane-scheffknecht.at"
EXCLUDE = re.compile(r"sugo|bolognese|sauce|soße|gutschein", re.I)
LD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def _url(slug: str) -> str:
    return f"{BASE}/product-page/{quote(unquote(slug))}"


def product_slugs(xml: str | None = None) -> list[str]:
    if xml is None:
        xml = get(f"{BASE}/store-products-sitemap.xml", raw=True, timeout=40).decode("utf-8", "replace")
    return [unquote(u).rstrip("/").split("/")[-1] for u in re.findall(r"<loc>([^<]*/product-page/[^<]+)</loc>", xml)]


def is_meal(slug_or_name: str) -> bool:
    return not EXCLUDE.search(unquote(slug_or_name))


def ld_product(page: str) -> dict | None:
    for m in LD.findall(page):
        try:
            d = json.loads(m)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            return d
    return None


def parse_desc(desc: str) -> dict:
    t = _html.unescape(desc or "").replace("\xa0", " ")
    z = re.search(r"Zutaten:\s*(.*?)\s*(?:\n|$)", t)
    s = re.search(r"(\d+)\s*g\s*,\s*(\d+)\s*Portionen", t)
    return {"ingredients": z.group(1).strip().rstrip(".") if z else None,
            "size": float(s.group(1)) if s else None,
            "portions": int(s.group(2)) if s else None,
            "portions_note": (re.search(r"\d+\s*g\s*,\s*([^\n]*Portionen[^\n]*)", t).group(1).strip().rstrip(".") if s else None)}


def parse(page: str, slug: str) -> Product | None:
    d = ld_product(page)
    if not d or not is_meal(slug) or not is_meal(d.get("name") or ""):
        return None
    off = d.get("Offers") or d.get("offers") or {}
    price = float(off["price"]) if off.get("price") else None
    x = parse_desc(d.get("description") or "")
    size = x["size"]
    imgs = [i.get("contentUrl") for i in (d.get("image") or []) if isinstance(i, dict) and i.get("contentUrl")]
    return Product(
        source="scheffknecht",
        store=STORE,
        name=re.sub(r"\s+", " ", d.get("name") or "").strip(),
        brand="Ariane Scheffknecht",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
        size_g=size,
        nutrition_100g={},
        ean=None,
        image_url=imgs[0] if imgs else None,
        producer=PRODUCER,
        category="Fertiggericht",
        source_url=off.get("url") or _url(slug),
        source_id=unquote(slug),
        extra={
            "slug": unquote(slug),
            "in_stock": (off.get("availability") or "").endswith("InStock"),
            "ingredients": x["ingredients"],
            "portions": x["portions"],
            "portions_note": x["portions_note"],
            "images": imgs,
            "price_note": "Preis je Glas inkl. USt lt. Produktseite (schema.org Offer)",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(slug_or_url: str, page_html: str | None = None) -> Product | None:
    slug = unquote(slug_or_url.strip().rstrip("/").split("/")[-1])
    if not is_meal(slug):
        return None
    if page_html is None:
        try:
            page_html = get(_url(slug), raw=True, headers={"Accept": "text/html"}, timeout=40).decode("utf-8", "replace")
        except Exception:
            return None
    return parse(page_html, slug)


class Scheffknecht(Adapter):
    id = "scheffknecht"
    store = STORE
    homepage = BASE
    notes = ("Live: Ariane Scheffknecht (Lustenau, Vorarlberg) Wix webshop — public store-products sitemap + product-page "
             "schema.org JSON-LD: 8 pasteurised jar meals 470–480 g (curries, chilis, dal, Gerstensuppen; 13,50–14,00 €) with "
             "ingredients, portions, availability, photos; Ragù alla Bolognese (sauce) excluded; no nutrition/GTIN; "
             "shipping fee not published, free from 12 jars; 1 + n requests, 1 s apart")

    def fetch(self, category="ready-meals", limit=50):
        out = []
        for s in product_slugs():
            if len(out) >= limit:
                break
            p = product(s) if is_meal(s) else None
            if p:
                out.append(p)
        return out

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for p in self.fetch():
            hay = f"{p.name} {p.extra.get('slug')} {p.extra.get('ingredients') or ''}".lower()
            if all(w in hay for w in words):
                out.append(p)
        return out[:limit]
