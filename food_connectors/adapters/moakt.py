"""Moakt.at — online shop of the regional farmers' market 'MoaktLaden' in Weiz (Steiermark), run by the association
'Weiz is(s)t regional – Verein zur Steigerung der regionalen Lebensmittelversorgung und -qualität im Genussraum Weiz'
(Vereinssitz Hauptplatz 7, 8160 Weiz; ZVR 1009369655; UID ATU80009358, VIES valid 2026-10-25). Ready meals come from
several regional producers ('Moakt-Betriebe'):
  * Robert kocht (Thannhausen) — pre-cooked, blast-frozen dishes in jars / packs (Ragouts, Curry, Suppe, Teigtaschen)
  * Qualitätsfleischerei Feiertag GmbH (Weiz) — 'mein Glas' essfertig 400 g (Gulasch, Gulaschsuppe, Beuschelsuppe, Chili)
  * Gemisch GesbR (Passail) — Wels aquaponics: Fisch-Suppe, Wels-Curry 430 ml
  * Hirsch und mehr... (Silvia und Bernhard Hausleitner, Weiz) — Wildragout im Glas 400 ml
  * Biohof Hirschbauer (Familie Trieb, Passail) — eingekochte Beuschelsuppe, Zwiebelsuppe (no photo, no size published)

Source (public, no login/cookies; GrandNode shop; robots.txt ``User-agent: *`` disallows only admin/cart/checkout/
customer/… paths, none used): the vendor pages ``/<vendor-slug>`` (product grid with name, price, product URL; every
vendor fits on one page) → product pages (schema.org microdata ``itemprop=price`` + ``itemprop=description``, gallery
``/content/images/thumbs/<id>_<slug>_550.*``). 1 request per second.
Ready meals = finished dishes and soups; excluded sides (Spätzle, Knödel, Schupfnudeln, Gnocchi, Rotkraut, Kürbisgemüse),
sauces/fonds (Sugo, Bolognese, Gulaschsaft, Kraftsuppe), spreads, fats, sausages, bread, salads, gift boxes.
No nutrition and no GTIN are published → never estimated.
Delivery: click & collect in the MoaktLaden (Florianigasse 5, 8160 Weiz, daily 5–23 h) or home delivery every Friday
in the Weiz area only (7 € fee, free from 70 € order value) — no parcel shipping, not Linz.
"""
from __future__ import annotations
import html as _html, re, time
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://moakt.at"
STORE = "Online: Moakt.at (Weiz)"
VENDORS = {
    "robert-kocht": ("Robert kocht", "Robert kocht, 8160 Thannhausen (Steiermark)"),
    "qualitaetsfleischerei-feiertag": ("mein Glas (Feiertag)", "Qualitätsfleischerei Feiertag GmbH, 8160 Weiz (Steiermark)"),
    "gemisch": ("Gemisch", "Gemisch GesbR, 8162 Passail (Steiermark)"),
    "hirsch-und-mehr": ("Hirsch und mehr...", "Hirsch und mehr... (Silvia und Bernhard Hausleitner), 8160 Weiz (Steiermark)"),
    "biohof-hirschbauer": ("Biohof Hirschbauer", "Biohof Hirschbauer (Familie Trieb), 8162 Passail (Steiermark)"),
}
SHIPPING_NOTE = ("Click & Collect im MoaktLaden (Florianigasse 5, 8160 Weiz, täglich 5–23 Uhr, Abholung am Folgetag) oder "
                 "Hauszustellung jeden Freitag ab 14 Uhr nur im Raum Weiz (Bestellschluss Do 15 Uhr); Zustellgebühr 7 €, "
                 "ab 70 € Bestellwert frei; kein Paketversand")
MEAL = re.compile(r"ragout|curry|suppe|gulasch|chili|teigtaschen", re.I)
EXCLUDE = re.compile(r"gulaschsaft|kraftsuppe|sugo|bolognese|suppenkr|suppenpulver|suppennudel|gutschein", re.I)
GRID = re.compile(r'<a class="title" href="(/[^"]+)">([^<]+)</a>.*?<span class="price">\s*([^<]+?)\s*</span>', re.S)


def _text(h: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).replace("\xa0", " ").strip()


def _fetch(path: str) -> str:
    return get(BASE + path, raw=True, headers={"Accept": "text/html"}, timeout=40).decode("utf-8", "replace")


def is_meal(name: str) -> bool:
    return bool(MEAL.search(name or "")) and not EXCLUDE.search(name or "")


def grid(vendor_html: str) -> list[dict]:
    out = []
    for u, n, p in GRID.findall(vendor_html):
        m = re.search(r"([\d.]+),(\d\d)", p)
        out.append({"path": u, "name": re.sub(r"\s+", " ", _html.unescape(n)).strip(),
                    "price": float(m.group(1).replace(".", "") + "." + m.group(2)) if m else None})
    return out


def parse_product(page: str, path: str, vendor: str) -> dict:
    price = re.search(r'itemprop="price" content="([\d.]+)"', page)
    d = re.search(r'itemprop="description"[^>]*>(.*?)</div>', page, re.S)
    desc = _text(d.group(1)) if d else ""
    own = desc.split("Da kommts her")[0].split("Mehr Interessantes über uns")[0].strip()
    imgs = re.findall(r'/content/images/thumbs/[0-9a-f]{24}_[^"\' ]+_550\.(?:jpe?g|png|webp)', page)
    name = re.search(r'<a class="title"|<h1[^>]*>(.*?)</h1>', page, re.S)
    z = re.search(r"Zutaten\s*[:|]\s*(.*?)(?:\s+(?:Mehr Interessantes|Serviervorschlag|Von hier kommen)|$)", own, re.S)
    return {"path": path, "vendor": vendor, "price": float(price.group(1)) if price else None,
            "description": own, "ingredients": z.group(1).strip(" .") if z else None,
            "image": BASE + imgs[0] if imgs else None}


def _size(name: str, desc: str) -> tuple[float | None, str | None]:
    for s in (name, desc):
        m = re.search(r"(\d{3,4})\s*(g|ml)\b", s or "")
        if m:
            return float(m.group(1)), m.group(1) + " " + m.group(2)
    return None, None


def to_product(x: dict) -> Product | None:
    if not is_meal(x["name"]):
        return None
    brand, producer = VENDORS[x["vendor"]]
    name = re.sub(r"^mein Glas - ", "", x["name"]).split(" | ")[0].strip()
    size, size_label = _size(x["name"], x.get("description", ""))
    price = x.get("price")
    slug = x["path"].strip("/")
    return Product(
        source="moakt", store=STORE, name=name, brand=brand, price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit=("l" if size_label and size_label.endswith("ml") else "kg") if price and size else None, size_g=size, nutrition_100g={}, ean=None,
        image_url=x.get("image"), producer=producer, category="Fertiggericht",
        source_url=BASE + x["path"], source_id=slug,
        extra={"vendor": x["vendor"], "size_label": size_label, "description": x.get("description"),
               "ingredients": x.get("ingredients"), "price_note": "Preis inkl. USt lt. moakt.at (schema.org itemprop=price)",
               "shipping_note": SHIPPING_NOTE},
    )


def all_products(pages: dict | None = None, delay: float = 1.0) -> list[Product]:
    """pages: optional {path: html} fixture map (vendor paths '/<slug>' and product paths)."""
    def fetch(p):
        if pages is not None:
            return pages[p]
        time.sleep(delay)
        return _fetch(p)
    out = []
    for v in VENDORS:
        for g in grid(fetch("/" + v)):
            if not is_meal(g["name"]):
                continue
            x = parse_product(fetch(g["path"]), g["path"], v) | {"name": g["name"]}
            x["price"] = x["price"] or g["price"]
            p = to_product(x)
            if p:
                out.append(p)
    return out


def product(id_or_name: str, pages: dict | None = None) -> Product | None:
    key = id_or_name.strip().rstrip("/").split("/")[-1].lower()
    for p in all_products(pages):
        if key == p.source_id.lower() or key in p.name.lower():
            return p
    return None


class Moakt(Adapter):
    id = "moakt"
    store = STORE
    homepage = BASE
    notes = ("Live: Moakt.at (Weiz is(s)t regional Verein, MoaktLaden Weiz, Stmk) GrandNode shop — vendor grids + product pages "
             "(schema.org price/description, photos) → ~15 regional ready meals from Robert kocht (frozen Ragouts/Curry/Suppe/"
             "Teigtaschen), Feiertag 'mein Glas' 400 g, Gemisch Wels-Curry/Fisch-Suppe, Hirsch und mehr Wildragout, Biohof "
             "Hirschbauer soups; no nutrition/GTIN; click & collect Weiz or Friday delivery Raum Weiz (7 €, free from 70 €)")

    def fetch(self, category="ready-meals", limit=50):
        return all_products()[:limit]

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = [p for p in all_products() if all(w in f"{p.name} {p.brand} {p.extra.get('ingredients') or ''}".lower() for w in words)]
        return out[:limit]
