"""Egle (egleshop.at) — shelf-stable canned/jarred ready meals and soups, mostly organic (BIO), sold in an
Austria-only Shopware 6 webshop. Operator per Impressum: Wilhelm Egle GmbH, Runastraße 3, 6800 Feldkirch (Austrian
office of the German GmbH; HRB 6630, Registergericht Memmingen, Gerichtsstand Neu-Ulm; Geschäftsführer Carsten Rocholl;
USt-IdNr. DE130855821 — EU VIES valid 2026-10-25, name/address not disclosed; Öko-Kontrollstelle DE-ÖKO-001;
no Austrian Firmenbuch number; GLEIF: no LEI).

Source (public Shopware 6 shop; /robots.txt answers 404 = no rules): category page ``/Lebensmittel/Fertiggerichte-Fisch/``
(all sub-categories, 82 listings) + ``/Lebensmittel/Suppen-Sossen/Eintoepfe/`` → product pages (schema.org microdata:
name, price incl. MwSt., SKU, price-unit content, ``itemprop=ingredients``, ``itemprop=nutritionalinfo`` table per 100 g,
og:image packshot ``*_DE-DE_F01.webp``; buy button vs. 'momentan nicht lieferbar'). 1 request/s via the polite gate.
Kept: wet, heat-and-eat Eintöpfe, Gerichte and Suppen. Excluded: all 2 x / 3 x / Sparpaket multipacks (bundles), fish
preserves (Thunfisch, Hering, Makrele, Lachsfilets, Forellen, Bückling, Lachspastete/-salat), Sauce Bolognese, dry mixes
(Steinpilz-Risotto, Bulgurpfanne, Vegetarisches Hack, Kartoffel-Püree, Grünkern-Bratlinge, Pancakes, Graupen-/Zwiebelsuppe,
Figur-Balance, Brühen/Bouillons/Delikatess-Suppe), Wild-Preiselbeeren.
Shipping (Lieferung): only within Austria; minimum order 25 €; 4,95 € per order, free from 75 €; 5–7 working days.
No GTIN published.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.egleshop.at"
STORE = "Online: Egle"
BRAND = "Egle"
OPERATOR = ("Wilhelm Egle GmbH, Runastraße 3, 6800 Feldkirch (HRB 6630 AG Memmingen, USt-IdNr. DE130855821)")
SHIPPING_NOTE = ("Lieferung nur innerhalb Österreichs; Mindestbestellwert 25 €; Versand 4,95 €, "
                 "versandkostenfrei ab 75 €; Lieferzeit 5–7 Werktage")
SHIPPING_AT = 4.95
CATEGORIES = ("Lebensmittel/Fertiggerichte-Fisch/", "Lebensmittel/Suppen-Sossen/Eintoepfe/")
EXCLUDE = re.compile(
    r"-\d+-x-|Sparpaket|Thunfisch|Hering|Makrele|Lachsfilet|Lachspastete|Lachssalat|Forellen|Buecklings|Sauce-Bolognese|"
    r"Risotto|Bulgurpfanne|Vegetarisches-Hack|Pueree|Bratlinge|Pancakes|Preiselbeeren|Graupensuppe|Zwiebelsuppe|"
    r"Figur-Balance|Bruehe|Bouillon|Delikatess-Suppe", re.I)
_N = r"(\d+(?:[.,]\d+)?)"
NUT = (("kcal", r"Energie:?\s*" + _N + r"\s*kJ\s*/\s*" + _N + r"\s*kcal"),
       ("fat", r"\bFett:?\s*" + _N + r"\s*g"), ("satfat", r"(?<!un)gesättigte Fettsäuren:?\s*" + _N + r"\s*g"),
       ("carbs", r"Kohlenhydrate:?\s*" + _N + r"\s*g"), ("sugar", r"Zucker:?\s*" + _N + r"\s*g"),
       ("fiber", r"Ballaststoffe:?\s*" + _N + r"\s*g"), ("protein", r"Eiwei(?:ß|ss):?\s*" + _N + r"\s*g"),
       ("salt", r"\bSalz:?\s*" + _N + r"\s*g"))


def _f(s):
    return float(s.replace(".", "").replace(",", ".")) if s and "," in s else (float(s) if s else None)


def _text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).replace("\xa0", " ").strip()


def _html_of(url: str) -> str:
    return get(url, raw=True, timeout=40, headers={"Accept": "text/html"}).decode("utf-8", "replace")


def slug_of(x: str) -> str:
    return x.strip().rstrip("/").split("?")[0].split("#")[0].split("/")[-1]


def category_slugs(page_html: str) -> list[str]:
    out = []
    for u in re.findall(r'<a[^>]*href="https://www\.egleshop\.at/([^"/?#]+)"[^>]*class="product-name"', page_html or ""):
        if not EXCLUDE.search(u) and u not in out:
            out.append(u)
    return out


def parse(slug: str, page_html: str) -> Product | None:
    if not page_html:
        return None
    main = page_html.split("product-detail-cross-selling", 1)[0]
    m = re.search(r'<h1 class="product-detail-name"[^>]*>(.*?)</h1>', main, re.S)
    name = _text(m.group(1)) if m else None
    pr = re.search(r'<meta itemprop="price"\s+content="(\d+(?:\.\d+)?)"', main)
    if not name or not pr:
        return None
    price = float(pr.group(1))
    sku = re.search(r'itemprop="sku">\s*([^<\s]+)', main)
    unit = re.search(r'price-unit-content">\s*([\d.,]+)\s*(kg|g|ml|l|Liter)\s*<', main)
    size_g = unit_raw = None
    if unit:
        v, u = _f(unit.group(1)), unit.group(2)
        size_g = round(v * 1000, 1) if u in ("kg", "l", "Liter") else v
        unit_raw = "ml" if u in ("ml", "l", "Liter") else "g"
    if unit_raw == "g" and re.search(r"\d\s*ml\b", name):
        unit_raw = "ml"
    nb = re.search(r'itemprop="nutritionalinfo">(.*?)</table>', main, re.S)
    nt = _text(nb.group(1)) if nb else ""
    nut = {}
    for k, rx in NUT:
        mm = re.search(rx, nt)
        if mm:
            nut[k] = _f(mm.group(2) if k == "kcal" else mm.group(1))
    kj = re.search(r"Energie:?\s*" + _N + r"\s*kJ", nt)
    zi = re.search(r'itemprop="ingredients">(.*?)</div>', main, re.S)
    zt = re.sub(r"^Zutaten\s*:\s*", "", _text(zi.group(1))) if zi else ""
    land = re.search(r"Produktionsland:\s*([A-Za-zÄÖÜäöü]+)", zt)
    zt = re.split(r"\s*Produktionsland:", zt)[0]
    ing, _, prep = (x.strip() for x in zt.partition("Zubereitung:"))
    if not prep:
        mm = re.search(r"Zubereitung:\s*(.*?)(?:\s+Nährwerte\b|$)", _text(main))
        prep = mm.group(1) if mm else ""
    prep = re.split(r"\s*(?:Menü schließen|Zutaten\s*:)", re.sub(r"^(?:Menü schließen\s*)+", "", prep))[0].strip()[:300] or None
    ing = ing or None
    t = _text(main)
    pack = "Dose" if re.search(r"Dose", prep or "") else ("Glas" if re.search(r"\bGlas", (prep or "") + " " + t[:200]) else None)
    img = re.search(r'<meta property="og:image"\s+content="([^"]+)"', page_html)
    img = img.group(1) if img and re.search(r"[-_]F01\.", img.group(1)) else None
    in_stock = "btn-buy" in main and "product-outofstock" not in main
    return Product(
        source="egle", store=STORE, name=name, brand=BRAND, price_eur=price,
        unit_price_eur=round(price / size_g * 1000, 2) if size_g else None,
        unit=("l" if unit_raw == "ml" else "kg") if size_g else None, size_g=size_g,
        nutrition_100g=nut, ean=None, image_url=img, producer=OPERATOR, origin=land.group(1) if land else None, category="Fertiggericht",
        source_url=f"{BASE}/{slug}", source_id=sku.group(1) if sku else slug,
        extra={"kind": "Suppe" if re.search(r"suppe", name, re.I) else "Gericht", "size_unit": unit_raw,
               "kj_100": _f(kj.group(1)) if kj else None, "ingredients": ing, "prep": prep, "packaging": pack,
               "bio": name.upper().startswith("BIO "), "in_stock": in_stock,
               "price_basis": "inkl. MwSt. lt. Produktseite", "shipping_note": SHIPPING_NOTE})


def is_ready_meal(p: Product | None) -> bool:
    return bool(p and p.name and p.price_eur and p.size_g and not EXCLUDE.search(slug_of(p.source_url)))


def meal_slugs() -> list[str]:
    out = []
    for c in CATEGORIES:
        for s in category_slugs(_html_of(f"{BASE}/{c}")):
            if s not in out:
                out.append(s)
    return out


def product(slug_or_url: str) -> Product | None:
    s = slug_of(slug_or_url)
    if EXCLUDE.search(s):
        return None
    try:
        p = parse(s, _html_of(f"{BASE}/{s}"))
    except Exception:
        return None
    return p if is_ready_meal(p) else None


def all_products(limit: int = 500) -> list[Product]:
    out = []
    for s in meal_slugs()[:limit]:
        p = parse(s, _html_of(f"{BASE}/{s}"))
        if is_ready_meal(p):
            out.append(p)
    return out


class Egle(Adapter):
    id = "egle"
    store = STORE
    homepage = BASE
    notes = ("Live: public Shopware 6 category pages (Fertiggerichte & Fisch, Eintöpfe) + product pages (microdata "
             "price/SKU, Inhalt, Zutaten, Nährwerte per 100 g, F01 packshot, stock); shelf-stable BIO canned/jarred "
             "Eintöpfe, Gerichte & Suppen, Wilhelm Egle GmbH Feldkirch (DE GmbH, HRB 6630 Memmingen); AT-only delivery "
             "4,95 €, free from 75 €; multipacks, fish preserves, sauces and dry mixes excluded; no GTIN; 1 req/s")

    def fetch(self, category="ready-meals", limit=500):
        return all_products(limit)

    def search(self, q, limit=50):
        tr = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
        words = [w.lower().translate(tr) for w in re.findall(r"\w{3,}", q)]
        out = []
        for s in meal_slugs():
            if all(w in s.lower() for w in words):
                p = parse(s, _html_of(f"{BASE}/{s}"))
                if is_ready_meal(p):
                    out.append(p)
            if len(out) >= limit:
                break
        return out
