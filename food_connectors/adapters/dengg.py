"""Dengg Krapfen- und Knödelmanufaktur webshop (dengg.info) — handmade frozen Tyrolean Knödel, Schlutzkrapfen and
Kaskrapfen from Hall in Tirol. Operator per Impressum/VIES: dengg krapfen & knödel manufaktur GmbH, Innsbrucker Straße 11,
6060 Hall in Tirol (FN 376199 i LG Innsbruck; UID ATU67085156 — EU VIES valid 2026-10-25 with same name/address; GLEIF: no
LEI). Also stocked by BILLA, SPAR Tirol and Hörtnagl (Einzelhandel page).

Source (public; robots.txt disallows only /cgi-bin): shop category pages (Knödel, Schlutzkrapfen, Krapfen, Saisonale
Produkte) → product pages (schema.org Product JSON-LD: sku, image; visible price for the default pack 'EUR x zzgl.
Versandkosten'; pack variants) → linked official 'Produktdatenblatt' PDF (ingredients, allergens, nutrition per 100 g,
'Stück à N g'), parsed with poppler ``pdftotext -layout``. 1 request/s via the polite gate.
Kept: 26 savoury main dishes (6 Knödel, 17 Schlutz-/Schlipfkrapfen incl. Tiroler Tris and seasonal Bärlauch/Spargel,
3 Zillertaler Kaskrapfen, Brodakrapfen). Excluded: sweet Krapfen/Knödel (Marillen, Mohn, Zwetschken, Kiachl…), sides
(Semmelknödel, Sauerkraut, Erdäpfelblattl/-paunzen, Butterbrösel, Teigblattl).
Price: the page shows 'EUR x inkl. 10% MwSt zzgl. Versandkosten' (used); some renders show only the net price → ×1.10
and flagged. In the net render the schema.org offer price is net ×1.2; it is kept in extra only.
Shipping (Verpackung & Versand): frozen with dry ice, sent Wednesdays/delivered Thursdays; Austria 20,00 €, Germany 33,00 €;
PayPal only. No GTIN published.
"""
from __future__ import annotations
import html as _html, json, re, subprocess, tempfile
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.dengg.info"
STORE = "Online: Dengg Krapfen- und Knödelmanufaktur"
OPERATOR = "dengg krapfen & knödel manufaktur GmbH, Innsbrucker Straße 11, 6060 Hall in Tirol (FN 376199 i, UID ATU67085156)"
SHIPPING_NOTE = ("tiefgekühlt mit Trockeneis, Versand nur Mi / Zustellung Do (Bestellung bis Di 14 Uhr); "
                 "Versand Österreich 20,00 €, Deutschland 33,00 €; Zahlung nur PayPal")
SHIPPING_AT = 20.0
CATEGORIES = ["unsere-produkte/knoedel.html", "unsere-produkte/schlutzkrapfen.html", "unsere-produkte/krapfen.html",
              "unsere-produkte/saisonale-produkte.html"]
MEALS = {
    "kasnocken-4-stk--62240849", "kaspressknoedel-4-stk--62238307", "kuerbisknoedel-4-stk--62241432",
    "rohnenknoedel-4-stk--62238561", "spinatknoedel-4-stk--62241021", "tiroler-speckknoedel-4-stk--62239296",
    "osttiroler-schlipfkrapfen-15-stk--62237788", "schlipfkrapfen-qualitaet-tirol--76691362",
    "schlutzkrapfen-mit-bergkaesefuelle-15-stk--62238038", "schlutzkrapfen-mit-grammelfuelle-15-stk--67981171",
    "schlutzkrapfen-mit-graukasfuelle-15-stk--62237386", "schlutzkrapfen-mit-kartoffel-topfenfuelle-15-stk--62236842",
    "schlutzkrapfen-mit-kuerbisfuelle-15-stk--62235187", "schlutzkrapfen-mit-pfifferlingfuelle-15-stk--62236003",
    "schlutzkrapfen-mit-speckfuelle-15-stk--62235518", "schlutzkrapfen-mit-spinatfuelle-15-stk--62207958",
    "schlutzkrapfen-mit-spinatfuelle-15-stk-vegan--62235689", "schlutzkrapfen-mit-steinpilzfuelle-15-stk--62235819",
    "schlutzkrapfen-mix-15-stk--62236995", "tiroler-tris-12-stk--62237075",
    "schlutzkrapfen-mit-baerlauchfuelle-15-stk--62237616", "schlutzkrapfen-mit-spargelfuelle-15-stk--62236670",
    "zillertaler-kaskrapfen-10-stk--62242065", "zillertaler-kaskrapfen-vorgebacken-12-stk--62919715",
    "mini-zillertaler-kaskrapfen-15-stk--62241888", "brodakrapfen-10-stk--62920003"}
# Kürbis-/Rohnenknödel: datasheet link 404 → pack weight from the packshot label '400 g' (vision-checked 2026-10-25)
PACK_G = {"kuerbisknoedel-4-stk--62241432": 400.0, "rohnenknoedel-4-stk--62238561": 400.0}
PIECES = {"schlipfkrapfen-qualitaet-tirol--76691362": 15}


def _text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _num(s):
    return float(s.replace(",", ".")) if s else None


def slug_of(x: str) -> str:
    x = x.strip().rstrip("/").split("/")[-1]
    x = re.sub(r"-de\.html$|\.html$", "", x)
    if x.isdigit():
        return next((m for m in MEALS if m.endswith("--" + x)), x)
    return x


def meal_slugs(pages: list[str]) -> list[str]:
    out = []
    for h in pages:
        for s in re.findall(r'href="https://www\.dengg\.info/([a-z0-9-]+--\d+)-de\.html"', h):
            if s in MEALS and s not in out:
                out.append(s)
    return out


def parse_datasheet(txt: str) -> dict:
    def g(rx):
        m = re.search(rx, txt or ""); return _num(m.group(1)) if m else None
    e = re.search(r"Brennwert\s+([\d.,]+)\s*kJ\s*/\s*([\d.,]+)\s*kcal", txt or "")
    nut = {k: v for k, v in {"energy_kj": _num(e.group(1)) if e else None, "energy_kcal": _num(e.group(2)) if e else None,
           "fat": g(r"\bFett\s+([\d,]+)\s*g"), "saturated_fat": g(r"gesättigte Fettsäuren\s+([\d,]+)\s*g"),
           "carbohydrates": g(r"Kohlenhydrate\s+([\d,]+)\s*g"), "sugars": g(r"davon Zucker\s+([\d,]+)\s*g"),
           "proteins": g(r"Eiweiß\s+([\d,]+)\s*g"), "salt": g(r"Salz\s+([\d,]+)\s*g")}.items() if v is not None}
    z = re.search(r"ZUTATEN\s*(.+?)(?:ALL?ERGENE|DURCHSCHNITTLICHE)", txt or "", re.S)
    ingr = re.sub(r"\s+", " ", re.sub(r"\s{3,}\S[^\n]*", " ", z.group(1))).strip() if z else None
    return {"nutrition": nut, "unit_g": g(r"Stück\s*à\s*([\d,]+)\s*g"), "ingredients": ingr}


def pdf_text(url: str) -> str:
    b = get(url, raw=True, timeout=40)
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(b); f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True).stdout


def parse(slug: str, page: str, sheet: str | None) -> Product | None:
    if slug not in MEALS:
        return None
    ld = [json.loads(m) for m in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', page, re.S)]
    p = next((d for d in ld if d.get("@type") == "Product"), {})
    txt = _text(page)
    vis = re.search(r"EUR ([\d.,]+) (inkl\. (\d+)% MwSt )?zzgl", txt)
    val = _num(vis.group(1).replace(".", "").replace(",", ".")) if vis else None
    if vis and vis.group(2):
        price, basis = val, f"brutto inkl. {vis.group(3)} % MwSt lt. Shop"
    elif val:  # page rendered without VAT note (net view) → Austrian food VAT 10 % added, flagged
        price, basis = round(val * 1.10, 2), "Shop zeigte Nettopreis %.2f € → ×1,10 (10 %% MwSt Lebensmittel) berechnet" % val
    else:
        price, basis = None, None
    ldp = (p.get("offers") or [{}])[0].get("price")
    desc = _text(p.get("description", ""))
    ds = parse_datasheet(sheet) if sheet else {"nutrition": {}, "unit_g": None, "ingredients": None}
    name = _html.unescape(p.get("name") or "").replace('"', "").strip()
    pm = re.search(r"(\d+) Stk", name)
    pieces = int(pm.group(1)) if pm else PIECES.get(slug)
    size = PACK_G.get(slug) or (round(pieces * ds["unit_g"], 1) if pieces and ds["unit_g"] else None)
    variants = [v.strip() for v in re.findall(r'aufpreis-typ="[^"]*">([^<]+)', page)]
    low = (desc + " " + name).lower()
    return Product(
        source="dengg", store=STORE, name=name, brand="Dengg", price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None, unit="kg" if price and size else None,
        size_g=size, nutrition_100g=ds["nutrition"], ean=None, image_url=p.get("image"),
        producer="dengg krapfen & knödel manufaktur GmbH (Hall in Tirol)", category="Fertiggericht",
        source_url=f"{BASE}/{slug}-de.html", source_id=str(p.get("sku") or slug.split("--")[-1]),
        extra={"slug": slug, "pieces": pieces, "unit_g": ds["unit_g"], "variants": variants, "ingredients": ds["ingredients"],
               "in_stock": "InStock" in json.dumps(p.get("offers") or []), "description": desc[:400],
               "veg": "vegetarisch" in low or "vegan" in low, "vegan": "vegan" in low,
               "ld_offer_price": float(ldp) if ldp else None, "datasheet": bool(sheet),
               "price_basis": basis,
               "price_note": "Shoppreis der Standardpackung; schema.org-Angebotspreis nur Info (in der Netto-Ansicht = Netto ×1,2)",
               "shipping_note": SHIPPING_NOTE})


def fetch_one(slug: str) -> Product | None:
    slug = slug_of(slug)
    if slug not in MEALS:
        return None
    page = get(f"{BASE}/{slug}-de.html", raw=True).decode("utf-8", "ignore")
    m = re.search(r'href="([^"]+\.pdf)"', page)
    sheet = None
    if m:
        try:
            sheet = pdf_text(m.group(1))
        except Exception:
            sheet = None
    return parse(slug, page, sheet)


def all_products(limit: int = 50) -> list[Product]:
    pages = [get(f"{BASE}/{c}", raw=True).decode("utf-8", "ignore") for c in CATEGORIES]
    return [p for p in (fetch_one(s) for s in meal_slugs(pages)[:limit]) if p]


def product(slug_or_url: str) -> Product | None:
    return fetch_one(slug_or_url)


class Dengg(Adapter):
    id = "dengg"
    store = STORE
    homepage = BASE
    notes = ("Live: Dengg Krapfen- und Knödelmanufaktur (Hall in Tirol; FN 376199 i, UID ATU67085156) — category pages + "
             "product JSON-LD + Produktdatenblatt PDFs: 26 frozen Knödel/Schlutzkrapfen/Kaskrapfen with nutrition per 100 g, "
             "piece weight, ingredients, packshots; no GTIN; frozen shipping AT 20 €, DE 33 € (Wed)")

    def fetch(self, category="ready-meals", limit=50):
        return all_products(limit)

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        pages = [get(f"{BASE}/{c}", raw=True).decode("utf-8", "ignore") for c in CATEGORIES]
        tr = lambda w: w.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        hits = [s for s in meal_slugs(pages) if all(tr(w) in s for w in words)]
        return [p for p in (fetch_one(s) for s in hits[:limit]) if p]
