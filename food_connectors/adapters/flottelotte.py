"""Flotte Lotte (flottelottezwettl.at) — vegan, gluten- and lactose-free jar soups and stews made from rescued surplus
vegetables in Zwettl (Waldviertel, NÖ). Operator per Impressum/VIES: Flotte Lotte GmbH, Pater Werner Deibl Strasse 5,
3910 Zwettl (FN 550284 t, LG Krems an der Donau; UID ATU76539079 — EU VIES valid 2026-10-25, name 'Flotte Lotte GmbH',
address 'Pater Werner Deibl-Straße 5, AT-3910 Zwettl-NÖ'; GLN 9110029937544; GLEIF: no LEI).

Source (public JTL-Shop; robots.txt ``User-agent: * / Disallow:`` = everything allowed): category pages ``/Eintoepfe``
and ``/Suppen`` → product pages (schema.org microdata: sku 'GKxxxx', price, availability, packshot; visible
'Inhalt: 380,00 g', 'Nährwerte:' table per 100 g, ingredient line, storage text). 1 request/s via the polite gate.
Kept: savoury Eintöpfe (Currys, Gulasch, Dhal, Linseneintopf) and Suppen. Excluded: Sugos (pasta sauces), Chutneys,
Fruchtaufstriche, Fruchtmus, Röster, Sonstiges (Suppengewürz, Grillsauce, Brotaufstrich), Probier-/Geschenksets.
Shipping (Versandinformationen): chilled express Tue–Thu, AT via DHL: 9,90 € below 75 €, 7,90 € for 75–99,99 €, free
from 100 €; DE via Go Express 19,90/17,90 €. No GTIN published on the shop (the legacy WooCommerce shop under /wp/ is
not used).
"""
from __future__ import annotations
import html as _html, re, time
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://flottelottezwettl.at"
STORE = "Online: Flotte Lotte"
OPERATOR = "Flotte Lotte GmbH, Pater Werner Deibl Strasse 5, 3910 Zwettl (FN 550284 t, UID ATU76539079)"
SHIPPING_NOTE = ("gekühlter Expressversand Di–Do (DHL); Österreich 9,90 € unter 75 €, 7,90 € ab 75 €, "
                 "versandkostenfrei ab 100 €; Deutschland 19,90 € bzw. 17,90 € ab 75 €")
SHIPPING_AT = 9.9
CATEGORIES = {"Eintoepfe": "Eintopf", "Suppen": "Suppe"}
_SKIP = {"Chutneys", "Eintoepfe", "Fruchtaufstriche", "Fruchtmus", "Probier-Geschenksets", "Roester", "Sonstiges",
         "Sugos", "Suppen", "AGB", "AGB-Gewinnspiel", "Allergene", "Baumpatenschaft", "Baumpatenschaftspakete",
         "Datenschutz", "FAQ", "Geschenkbox-3er", "Geschenkbox-5er", "Impressum", "Kontakt", "Lebensmittelueberschuesse",
         "News", "Online-Widerrufsformular", "Passwort-vergessen", "Probierset-Sugo-Chutney", "Probierset-Suppen",
         "Registrieren", "Sitemap", "Versandinformationen", "Warenkorb", "Widerrufsrecht", "Wir-ueber-uns",
         "Zahlungsmoeglichkeiten"}
_N = r"(\d+(?:[.,]\d+)?)"
NUT = (("kcal", r"Brennwert\s+" + _N + r"\s*(?:Joule|kJ)\s*/\s*" + _N + r"\s*kcal"),
       ("fat", r"\bFett\s+" + _N + r"\s*g"), ("satfat", r"davon gesättigt\w*\s+" + _N + r"\s*g"),
       ("carbs", r"Kohlenhydrate\s+" + _N + r"\s*g"), ("sugar", r"davon Zucker\s+" + _N + r"\s*g"),
       ("fiber", r"Ballaststoffe\s+" + _N + r"\s*g"), ("protein", r"Eiwei(?:ß|ss)\s+" + _N + r"\s*g"),
       ("salt", r"\bSalz\s+" + _N + r"\s*g"))


def _f(s):
    return float(s.replace(",", ".")) if s else None


def _text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).replace("\xa0", " ").strip()


def _html_of(url: str) -> str:
    return get(url, raw=True, timeout=40, headers={"Accept": "text/html"}).decode("utf-8", "replace")


def slug_of(x: str) -> str:
    return x.strip().rstrip("/").split("?")[0].split("/")[-1]


def category_slugs(page_html: str) -> list[str]:
    out = []
    for s in re.findall(r'href="https://flottelottezwettl\.at/([A-Za-z0-9\-]+)"', page_html or ""):
        if s not in _SKIP and s not in out:
            out.append(s)
    return out


def parse(slug: str, page_html: str, kind: str | None = None) -> Product | None:
    if not page_html:
        return None
    main = page_html.split("Kunden kauften dazu", 1)[0]
    t = _text(main)
    m = re.search(r'<h1[^>]*>(.*?)</h1>', main, re.S)
    name = _text(m.group(1)) if m else None
    cat = re.search(r"Kategorie:\s*(\w+)", t)
    catname = cat.group(1) if cat else None
    if kind is None:
        kind = {"Eintöpfe": "Eintopf", "Suppen": "Suppe"}.get(catname or "")
    if not name or not kind:
        return None
    sku = re.search(r"Artikelnummer:\s*(GK\d+)", t)
    pr = re.search(r'itemprop="price"\s+content="(\d+(?:\.\d+)?)"', main)
    price = float(pr.group(1)) if pr else None
    size = re.search(r"Inhalt:\s*" + _N + r"\s*(g|ml)", t)
    size_g = _f(size.group(1)) if size else None
    unit = size.group(2) if size else None
    nut = {}
    blk = t.split("Nährwerte:", 1)[1] if "Nährwerte:" in t else ""
    for k, rx in NUT:
        mm = re.search(rx, blk)
        if mm:
            nut[k] = _f(mm.group(2) if k == "kcal" else mm.group(1))
    kj = re.search(r"Brennwert\s+" + _N + r"\s*(?:Joule|kJ)", blk)
    img = re.search(r'<meta property="og:image" content="([^"]+)"', page_html)
    ingredients = None
    zi = re.search(r"Kategorie:\s*\w+\s+(.*?)\s+\d+,\d{2}\s*€", t)
    if zi:
        ingredients = zi.group(1).strip()
    desc = re.search(r"Beschreibung\s+(.*?)\s+Produkteigenschaft", t)
    stock = re.search(r'itemprop="availability"\s+href="https://schema\.org/(\w+)"', main)
    return Product(
        source="flottelotte", store=STORE, name=name, brand="Flotte Lotte", price_eur=price,
        unit_price_eur=round(price / size_g * 1000, 2) if price and size_g else None,
        unit=("l" if unit == "ml" else "kg") if price and size_g else None, size_g=size_g,
        nutrition_100g=nut, ean=None, image_url=img.group(1) if img and "keinBild" not in img.group(1) else None, producer=OPERATOR,
        origin="AT (Niederösterreich, Zwettl)", category="Fertiggericht",
        source_url=f"{BASE}/{slug}", source_id=sku.group(1) if sku else slug,
        extra={"kind": kind, "shop_category": catname, "size_unit": unit, "kj_100": _f(kj.group(1)) if kj else None,
               "ingredients": ingredients, "storage": desc.group(1).strip() if desc else None,
               "in_stock": (stock.group(1) == "InStock") if stock else None, "vegan": True, "glutenfrei": True,
               "laktosefrei": True, "price_basis": "inkl. 10 % USt. lt. Produktseite",
               "shipping_note": SHIPPING_NOTE, "packaging": "Glas"})


def is_ready_meal(p: Product | None) -> bool:
    return bool(p and p.name and p.price_eur and p.size_g)


def meal_slugs() -> list[tuple[str, str]]:
    out = []
    for c, kind in CATEGORIES.items():
        for s in category_slugs(_html_of(f"{BASE}/{c}")):
            if s not in [x for x, _ in out]:
                out.append((s, kind))
    return out


def product(slug_or_url: str) -> Product | None:
    s = slug_of(slug_or_url)
    if s in _SKIP:
        return None
    try:
        p = parse(s, _html_of(f"{BASE}/{s}"))
    except Exception:
        return None
    return p if is_ready_meal(p) else None


def all_products(limit: int = 500) -> list[Product]:
    out = []
    for s, kind in meal_slugs()[:limit]:
        p = parse(s, _html_of(f"{BASE}/{s}"), kind)
        if is_ready_meal(p):
            out.append(p)
    return out


class FlotteLotte(Adapter):
    id = "flottelotte"
    store = STORE
    homepage = BASE
    notes = ("Live: public JTL-Shop category pages (Eintöpfe, Suppen) + product pages (microdata price/SKU/stock/"
             "packshot, Inhalt, Nährwerte per 100 g, Zutaten); vegan jar soups & stews from rescued vegetables, "
             "Flotte Lotte GmbH Zwettl NÖ; chilled express AT 9,90 €, free from 100 €; no GTIN; 1 req/s")

    def fetch(self, category="ready-meals", limit=500):
        return all_products(limit)

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for s, kind in meal_slugs():
            if all(w in s.lower().replace("ue", "ü") or w in s.lower() for w in words):
                p = parse(s, _html_of(f"{BASE}/{s}"), kind)
                if is_ready_meal(p):
                    out.append(p)
            if len(out) >= limit:
                break
        return out
