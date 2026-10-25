"""Martina's Nudlkudlmudl (nudlkudlmudl.com) — hand-made Kärntner Nudeln (Kasnudel, Fleischnudel, Erdäpfelnudel …)
from the AMA-certified Nudelmanufaktur in Radenthein, Kärnten, sold chilled via Österreichische Post Frischeversand.

Source (public, no login/cookies; robots.txt ``User-agent: *`` disallows only ``/app/`` and ``/j/``, Crawl-Delay 5):
  * ``https://www.nudlkudlmudl.com/onlineshop/`` — one Jimdo page with every product as schema.org ``Product``
    microdata: name, description (Menge, Zutaten), Offer price (EUR incl. MwSt), availability, image, weight.
One request per fetch (well inside the crawl delay); ``/j/shop/info`` (shipping table) is robots-disallowed → not read.
Ready meals = filled Kärntner Nudeln (main dish, 5 pcs/600 g, cook before eating) + 'Kärntner Schweinsbraten Essfertig'.
Excluded: Kletzennudel (sweet dessert noodle), Bratlfett (spread), Oma's Glasl Kuchl Sugo Bolognese (pasta sauce).
No nutrition and no GTIN are published → never estimated.
Shipping: AT only, Post Frischeversand in a cooled box, free from 100 €; the shop page says the post now charges
19,90 € per parcel incl. box return (since 1.1.2026) passed on 1:1 — the exact customer fee sits on the disallowed
/j/ page → ``shipping_eur`` left empty, note kept.
Operator (Impressum /about/): Martina Hinteregger, Hauptstrasse 28, 9545 Radenthein (sole trader, no UID/FN published).
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.nudlkudlmudl.com"
SHOP = f"{BASE}/onlineshop/"
STORE = "Online: Martina's Nudlkudlmudl"
PRODUCER = "Martina's Nudlkudlmudl (Martina Hinteregger), Hauptstrasse 28, 9545 Radenthein, Kärnten"
SHIPPING_NOTE = ("Post Frischeversand nur innerhalb Österreichs, Thermokarton mit Kühlpads, 7–10 Tage nach Zahlungseingang; "
                 "versandkostenfrei ab 100 €; Versandkosten = Post-Tarif 1:1 (lt. Shop seit 1.1.2026 19,90 € je Paket inkl. "
                 "Box-Rückversand); Betrag im Shop-Checkout")
EXCLUDE = re.compile(r"kletzen|bratlfett|sugo|bolognese|gutschein", re.I)
BLOCK = re.compile(r'<div id="cc-m-product-(\d+)" itemscope="" itemtype="http://schema.org/Product">(.*?)<!-- end of div#cc-m-product-', re.S)


def _text(h: str) -> str:
    h = re.sub(r"<br\s*/?>|</p>", "\n", h)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in t.splitlines() if l.strip())


def _slug(name: str) -> str:
    s = name.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def is_meal(name: str) -> bool:
    return not EXCLUDE.search(name or "")


def parse_block(mid: str, b: str) -> dict:
    name = re.search(r'itemprop="name">(.*?)</h4>', b, re.S)
    desc = re.search(r'itemprop="description">(.*?)</div>', b, re.S)
    price = re.search(r'itemprop="price" content="([\d.]+)"', b)
    avail = re.search(r'itemprop="availability" content="(\w+)"', b)
    img = re.search(r'id="cc-product-superzoom-\d+" href="([^"]+)"', b)
    url = re.search(r'itemprop="url" content="([^"]+)"', b)
    wt = re.search(r'j-product-weight">\s*([\d,]+)\s*kg', b)
    d = _text(desc.group(1)) if desc else ""
    z = re.search(r"Zutaten\s*:\s*(.*)", d, re.S)
    if z:
        ingr = z.group(1)
    else:  # some products list ingredients without the 'Zutaten:' label after the Menge line
        ls = d.splitlines()
        k = next((i for i, l in enumerate(ls) if l.startswith("Menge")), None)
        ingr = " ".join(ls[k + 1:]) if k is not None else (ls[-1] if len(ls) > 1 else "")
    ingr = re.split(r"\s*Serviertipp", ingr)[0]
    menge = re.search(r"Menge\s*:\s*([^\n]*)", d)
    g = re.search(r"(\d+)\s*(?:Gramm|g)\b", d)
    return {
        "id": mid,
        "name": re.sub(r"\s+", " ", _html.unescape(name.group(1))).strip() if name else "",
        "price": float(price.group(1)) if price else None,
        "in_stock": bool(avail and avail.group(1) == "InStock"),
        "image": img.group(1) if img else None,
        "url": url.group(1).replace("//app/", "/app/") if url else SHOP,
        "size_g": float(g.group(1)) if g else (float(wt.group(1).replace(",", ".")) * 1000 if wt else None),
        "menge": menge.group(1).strip() if menge else None,
        "ingredients": re.sub(r"\s+", " ", ingr).strip(" .") or None,
    }


def blocks(page: str | None = None) -> list[dict]:
    if page is None:
        page = get(SHOP, raw=True, headers={"Accept": "text/html"}, timeout=40).decode("utf-8", "replace")
    return [parse_block(m, b) for m, b in BLOCK.findall(page)]


def to_product(x: dict) -> Product | None:
    if not x["name"] or not is_meal(x["name"]):
        return None
    price, size = x["price"], x["size_g"]
    return Product(
        source="nudlkudlmudl",
        store=STORE,
        name=x["name"],
        brand="Martina's Nudlkudlmudl",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
        size_g=size,
        nutrition_100g={},
        ean=None,
        image_url=x["image"],
        producer=PRODUCER,
        category="Fertiggericht",
        source_url=SHOP,
        source_id=_slug(x["name"]),
        extra={
            "jimdo_module": x["id"],
            "product_url": x["url"],
            "in_stock": x["in_stock"],
            "menge": x["menge"],
            "ingredients": x["ingredients"],
            "price_note": "Preis je Packung inkl. MwSt lt. Onlineshop (schema.org Offer)",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def all_products(page: str | None = None) -> list[Product]:
    return [p for p in (to_product(x) for x in blocks(page)) if p]


def product(id_or_name: str, page_html: str | None = None) -> Product | None:
    key = _slug(id_or_name.strip().rstrip("/").split("/")[-1])
    for p in all_products(page_html):
        if key in (p.source_id, p.extra["jimdo_module"]) or key in p.source_id:
            return p
    return None


class Nudlkudlmudl(Adapter):
    id = "nudlkudlmudl"
    store = STORE
    homepage = BASE
    notes = ("Live: Martina's Nudlkudlmudl (Radenthein, Kärnten) Jimdo onlineshop — one public page with schema.org Product "
             "microdata: hand-made Kärntner Nudeln 600 g/5 Stk. (Kasnudel, Fleischnudel, Erdäpfelnudel, Spinat-, Tomate-Mozzarella-, "
             "Bärlauchnudel; 12,90–13,90 €) + Schweinsbraten essfertig 250 g; Kletzennudel/Bratlfett/Sugo excluded; ingredients, "
             "availability, photos; no nutrition/GTIN; Post Frischeversand AT only, free from 100 €; 1 request")

    def fetch(self, category="ready-meals", limit=50):
        return all_products()[:limit]

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = [p for p in all_products() if all(w in f"{p.name} {p.extra.get('ingredients') or ''}".lower() for w in words)]
        return out[:limit]
