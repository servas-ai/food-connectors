"""Fleischerei Diechtl (diechtl-shop.at) — Fleischerei Diechtl Erich Ernst e.U., Inh. Erich Ernst Diechtl, Hauptstraße 31,
8983 Bad Mitterndorf (Steiermark, Salzkammergut; FN 338325m, LG Leoben; UID ATU41616104, VIES valid 2026-10-25
'Diechtl Erich jun', Bad Mitterndorf 31; no LEI in GLEIF): the butcher's own Shopware 6 webshop with a small
'Feinkost im Glas' category cooked in its own kitchen.

Source (public server-rendered HTML, no login/cookies; robots.txt allows everything except ``/*?``, /account, /checkout,
/widgets — only query-free URLs and ``/media/*?ts=`` images are used):
  * ``https://www.diechtl-shop.at/feinkost-im-glas/`` — category listing (4 jars à 390 g) → product URLs. One request.
  * ``https://www.diechtl-shop.at/<slug>`` — product page with schema.org Product JSON-LD (name, sku, price EUR,
    availability, description incl. 'Inhalt: 390 g im Glas', 'Lagerung', 'Haltbarkeit', image). 1 req/s.
Ready meals = Rindsgulasch im Glas only; excluded: Gulaschsaft and Bolognese (sauces) and Rinderbrühe (clear broth /
cooking base). The product page publishes no ingredients, nutrition or GTIN. The ingredient list below is transcribed
by hand from the label visible on the shop's own packshot (2026-10-25) and applied only while the live page still
carries the same image file (else left empty, never guessed). No nutrition on page or label → never estimated.
Shipping (Service-Informationen/Lieferung-Zahlung): within Austria, chilled parcel, 1–3 working days, 6,90 € flat below
70 €, free from 70 €; pick-up in Bad Mitterndorf Wed/Fri.
Photos: product JSON-LD image (single-jar packshot with 'DIECHTL Rindergulasch im GLAS' label); vision gate 2026-10-25 1/1.
"""
from __future__ import annotations
import html as _html, json, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.diechtl-shop.at"
CATEGORY = f"{BASE}/feinkost-im-glas/"
STORE = "Online: Fleischerei Diechtl"
PRODUCER = ("Fleischerei Diechtl Erich Ernst e.U., Hauptstraße 31, 8983 Bad Mitterndorf, Steiermark "
            "(FN 338325m, LG Leoben; UID ATU41616104)")
SHIPPING_EUR = 6.90
SHIPPING_NOTE = ("Kühlpaket innerhalb Österreichs, 1–3 Werktage; Versandpauschale 6,90 € unter 70 €, ab 70 € versandkostenfrei "
                 "(Service-Informationen/Lieferung-Zahlung); Abholung in Bad Mitterndorf Mi/Fr möglich")
EXCLUDE = re.compile(r"gulaschsaft|bolognese|bruehe|brühe", re.I)
# transcribed from the label on the shop's own packshot 2026-10-25 (see docstring); key = image file name
LABEL = {
    "5awdk5t8.png": {
        "label_name": "DIECHTL Rindergulasch im GLAS",
        "ingredients": ("50% Rind, Wasser, Zwiebel, Tomatenmark, WEIZENMEHL, Kochsalz, Rapsöl, Gewürze: Paprika, "
                        "SELLERIE, Majoran, Kümmel, Knoblauch, weißer Pfeffer"),
        "allergens": "A (Weizen), L (Sellerie) lt. Großschreibung auf dem Etikett",
        "storage_label": "Gekühlt lagern bei +2 °C bis +4 °C; nach dem Öffnen im Kühlschrank lagern und innerhalb von 2–3 Tagen verbrauchen",
    },
}


def _ld(page: str) -> dict | None:
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            d = json.loads(m)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            return d
    return None


def category_urls(page: str | None = None) -> list[str]:
    """Product URLs from the category's schema.org ItemList (fallback: product-name headline links)."""
    page = page if page is not None else get(CATEGORY, headers={"Accept": "text/html"}, raw=True, timeout=30).decode("utf-8", "replace")
    urls = []
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            d = json.loads(m)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "ItemList":
            urls += [i.get("url") for i in d.get("itemListElement") or [] if str(i.get("url", "")).startswith(BASE + "/")]
    if not urls:
        urls = re.findall(r'<h2 class="product-name-headline[^"]*">\s*<a href="(https://www\.diechtl-shop\.at/[a-z0-9-]+)"', page)
    return list(dict.fromkeys(urls))


def is_meal(url_or_name: str) -> bool:
    return not EXCLUDE.search(url_or_name)


def parse(page: str, url: str) -> Product | None:
    d = _ld(page)
    if not d:
        return None
    off = d.get("offers") or {}
    price = float(off["price"]) if off.get("price") is not None else None
    desc = d.get("description") or ""
    g = re.search(r"Inhalt:\s*(\d+)\s*g", desc)
    size = float(g.group(1)) if g else None
    img = (d.get("image") or [None])[0]
    lab = LABEL.get(img.split("?")[0].rsplit("/", 1)[-1]) if img else None
    sto = re.search(r"Lagerung:\s*([^\n]+)", desc)
    hb = re.search(r"Haltbarkeit:\s*([^\n]+)", desc)
    name = _html.unescape(d.get("name") or url.rsplit("/", 1)[-1]).strip()
    return Product(
        source="diechtl", store=STORE, name=name, brand="Fleischerei Diechtl", price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None, unit="kg" if price and size else None,
        size_g=size, nutrition_100g={}, ean=None, image_url=img, producer=PRODUCER,
        origin="AT (Rindfleisch aus Österreich; gekocht in der Fleischerei Diechtl, Bad Mitterndorf lt. Shop)",
        category="Suppe" if "suppe" in name.lower() else "Fertiggericht", source_url=url, source_id=d.get("sku") or url.rsplit("/", 1)[-1],
        extra={"sku": d.get("sku"), "product_id": d.get("productID"), "pack": f"Glas {int(size)} g" if size else "Glas",
               "availability": (off.get("availability") or "").rsplit("/", 1)[-1] or None,
               "ingredients": lab["ingredients"] if lab else None, "allergens": lab["allergens"] if lab else None,
               "ingredients_source": "Etikett auf dem Shop-Produktfoto (transkribiert 2026-10-25)" if lab else None,
               "label_storage": lab["storage_label"] if lab else None,
               "storage": sto.group(1).strip() if sto else None, "shelf_life": hb.group(1).strip() if hb else None,
               "price_note": "Preis je Glas inkl. MwSt. lt. Produktseite (JSON-LD); Etikett auf dem Foto zeigt einen älteren Preis",
               "shipping_note": SHIPPING_NOTE},
    )


def product(slug_or_url: str, page_html: str | None = None) -> Product | None:
    k = slug_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    url = f"{BASE}/{k}"
    if page_html is None:
        if url not in category_urls():
            return None
        page_html = get(url, headers={"Accept": "text/html"}, raw=True, timeout=30).decode("utf-8", "replace")
    return parse(page_html, url)


class Diechtl(Adapter):
    id = "diechtl"
    store = STORE
    homepage = BASE
    notes = ("Live: Fleischerei Diechtl webshop (Fleischerei Diechtl Erich Ernst e.U., Bad Mitterndorf, Steiermark): "
             "'Feinkost im Glas' heat-up jar meal (Rindsgulasch 390 g) with price, €/kg, availability, label ingredients, "
             "photo; Gulaschsaft/Bolognese (sauces) and Rinderbrühe excluded; Kühlpaket AT-wide 6,90 €, free from 70 €")

    def fetch(self, category="ready-meals", limit=50):
        return [p for p in (product(u) for u in category_urls() if is_meal(u)) if p][:limit]

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        return [p for p in self.fetch() if all(w in (p.name + " " + (p.extra.get("ingredients") or "")).lower() for w in words)][:limit]
