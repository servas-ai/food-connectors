"""myProduct (myproduct.at) — Austrian online marketplace for regional producers; category 'Fertiggerichte'.

Sources (public, no login/cookies; robots.txt ``User-agent: *`` disallows only Magento system paths,
/catalogsearch/, /checkout/, /customer/ … and sorted/filtered list URLs — category pages ``?p=N`` and
product pages are allowed):
  * category ``https://myproduct.at/lebensmittel/fertiggerichte?p=N`` (42 tiles per page) — the page's own
    GA4 dataLayer (``dl4Objects``: item_id = SKU, item_name, price, item_brand) + product tile links.
  * product page ``https://myproduct.at/<url-key>`` — schema.org JSON-LD Product (name, images, sku, brand,
    offers.price / availability) + the Magento 'Mehr Informationen' attribute table
    (``#product-attribute-specs-table``): Produzent, Herstellerangaben (producer name + address),
    Produzent Land, EAN Code, Produktmenge - Nettofüllmenge, Zutatenliste, Allergeninformation,
    Lagerhinweis, Mindesthaltbarkeitsdatum, Produkteigenschaft (bio/vegan …) and — when the producer
    publishes it — 'Durchschnittliche Nährwertangaben je 100 g' rows (Brennwert in kcal, Fett in g …).
Ready meals = items of the Fertiggerichte category that are finished dishes/soups (stocks/fonds, gravies,
pasta sauces, spreads/rillettes and dry mixes are excluded with a reason). Products whose page states
'Für dieses Produkt ist gesetzlich keine Nährwertkennzeichnung notwendig' keep ``nutrition_100g`` empty —
values are never estimated.
Shipping (myproduct.at/lieferung): 7,90 € per 10 kg gross weight within Austria; delivery usually within
24 h after dispatch (dispatch 1–2 or 2–5 working days).
Operator (myproduct.at/impressum): myProduct GmbH, Karl Kastner-Straße 1, 3910 Zwettl, FN 431059k
(Landesgericht Krems), UID ATU69436808. Polite ≥1 s between requests.
"""
from __future__ import annotations
import html as _html, json, re, time
from .base import Adapter
from ..http import get
from ..schema import Product, parse_size_g

BASE = "https://myproduct.at"
CATEGORY = f"{BASE}/lebensmittel/fertiggerichte"
STORE = "Online: myProduct"
OPERATOR = "myProduct GmbH, Karl Kastner-Straße 1, 3910 Zwettl, FN 431059k"
SHIPPING_NOTE = "7,90 € je 10 kg Gesamtgewicht innerhalb Österreichs (myproduct.at/lieferung)"
NUT_ROWS = {
    "Brennwert in kcal": "kcal", "Fett in g": "fat", "davon gesättigte Fettsäuren in g": "satfat",
    "Kohlenhydrate in g": "carbs", "davon Zucker in g": "sugar", "Ballaststoffe in g": "fiber",
    "Eiweiß in g": "protein", "Salz in g": "salt",
}
EXCLUDE = (
    (r"fonds?\b|bratensaft|bouillon|brühe|konzentrat", "Fond/Brühe/Bratensaft (Zutat, kein Gericht)"),
    (r"rillettes|aufstrich|pastete|feinkostsalat|schnal'?z", "Brotaufstrich/Feinkostsalat"),
    (r"mischung|\bmix\b|fertigmischung|basis\b|backmischung|trockenmischung|pizzabase|pizzaboden", "Trockenmischung/Teigbasis zum Selberzubereiten"),
    (r"\bsauce\b|\bsoße\b|\bsugo\b|pesto|al pomodoro|tomatensugo|feinkostsauce|saucenbinder", "Sauce/Sugo (Komponente)"),
    (r"^(?!.*(?:spaghetti|pasta|lasagne|nudel)).*bolognese", "Sauce/Sugo (Komponente, Bolognese ohne Pasta)"),
    (r"soja-?(?:schnetzel|granulat|flocken|geschnetzeltes)|soja geschnetzeltes|soja ?granulat|sonnenblumenhack|\bhack\b|salzlake|pork taste|tuna taste|better chicken|röstirolle", "Rohprodukt/Fleischersatz-Zutat (kein fertiges Gericht)"),
    (r"röster|hollerkoch|kompott|dessert|pudding|milchreis", "Süßspeise/Kompott"),
)


def _f(s):
    try:
        return float(str(s).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def _html_get(url: str) -> str:
    return get(url, raw=True, timeout=60, headers={"Accept": "text/html"}).decode("utf-8", "replace")


def parse_category(page_html: str) -> list[dict]:
    """Category page → [{sku, name, price, brand, url}] from the page's own dataLayer + tile links."""
    m = re.search(r"var dl4Objects = (\[.*?\]);\n", page_html, re.S)
    items = []
    if m:
        for o in json.loads(m.group(1)):
            items += (o.get("ecommerce") or {}).get("items") or []
    urls = re.findall(r'href="([^"]+)"\s+class="cs-product-tile__name-link product-item-link"', page_html)
    out = []
    for i, it in enumerate(items):
        out.append({"sku": it.get("item_id"), "name": _html.unescape(it.get("item_name") or "").strip(),
                    "price": it.get("price"), "brand": (it.get("item_brand") or "").strip() or None,
                    "url": urls[i] if i < len(urls) else None})
    return out


def category_items(max_pages: int = 20, delay: float = 1.0) -> list[dict]:
    seen, out = set(), []
    for p in range(1, max_pages + 1):
        items = parse_category(_html_get(f"{CATEGORY}?p={p}"))
        new = [i for i in items if i["sku"] not in seen]
        if not new:
            break
        seen |= {i["sku"] for i in new}
        out += new
        time.sleep(delay)
    return out


def attributes(page_html: str) -> dict:
    rows = re.findall(r'<th class="col label" scope="row">(.*?)</th>\s*<td class="col data"[^>]*>(.*?)</td>', page_html, re.S)
    return {_clean(k): _clean(v) for k, v in rows}


def _jsonld_product(page_html: str, url: str | None = None) -> dict:
    cands = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page_html, re.S):
        try:
            d = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            cands.append(d)
    if url:
        key = url.rstrip("/").split("/")[-1]
        for d in cands:
            if (d.get("url") or "").rstrip("/").split("/")[-1] == key:
                return d
    return cands[0] if cands else {}


def valid_ean(g: str | None) -> str | None:
    g = re.sub(r"\D", "", g or "")
    if len(g) not in (8, 13):
        return None
    d = list(map(int, g))
    w = [1, 3] if len(g) == 13 else [3, 1]
    if (10 - sum(v * w[i % 2] for i, v in enumerate(d[:-1])) % 10) % 10 != d[-1]:
        return None
    return g


def unit_size_g(name: str) -> float | None:
    """Single-pack size from the title ('… 350g - 6er Vorteilspack' → 350)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|ml|kg|l)\b", name or "", re.I)
    if not m:
        return None
    v = _f(m.group(1))
    return v * 1000 if m.group(2).lower() in ("kg", "l") else v


def pack_count(name: str) -> int:
    m = re.search(r"(\d+)er\s*(?:Vorteils)?pack", name or "", re.I)
    return int(m.group(1)) if m else 1


def atwater_check(n: dict) -> str | None:
    """'ok' | 'atwater_mismatch' | None (no table). kcal vs 4·KH + 4·Eiweiß + 9·Fett + 2·Ballaststoffe."""
    if n.get("kcal") is None or any(n.get(k) is None for k in ("fat", "carbs", "protein")):
        return None
    est = 4 * n["carbs"] + 4 * n["protein"] + 9 * n["fat"] + 2 * (n.get("fiber") or 0)
    return "ok" if abs(est - n["kcal"]) <= max(15.0, 0.2 * n["kcal"]) else "atwater_mismatch"


def exclusion(name: str, ingredients: str | None = None) -> str | None:
    for rx, why in EXCLUDE:
        if re.search(rx, name, re.I):
            return why
    if ingredients and re.match(r"\W*[\w-]*pulver", ingredients, re.I):
        return "Suppen-/Instantpulver (erste Zutat Pulver, kein Fertiggericht)"
    if re.search(r"ramen|instant.{0,10}(?:nudeln|noodles)|noodles", name, re.I):
        return None  # instant noodle meal (add hot water) — kept like other stores' 'Instant' rows
    u = unit_size_g(name)
    if pack_count(name) == 1 and u is not None and u > 2500:
        return "Großgebinde > 2,5 kg (Gastro/Rohstoff)"
    if u is not None and u < 100:
        return "Trocken-/Fix-Beutel < 100 g (Würzmischung oder Suppenpulver, kein Fertiggericht)"
    if ingredients is not None and u is not None and u < 300 and not re.search(r"wasser|gekocht", ingredients, re.I):
        return "Trockenprodukt zum Kochen (keine Wasser-/Kochzutat, Einzelpackung < 300 g)"
    if ingredients and re.match(r"\W*(?:\w+\s){0,2}(?:risottoreis|carnaroli|arborio|reis|bulgur|couscous|hirse|quinoa|nudeln|hartweizengrieß)\w*\*?°?\s*\(?(?:[5-9]\d|100)\s*[,.]?\d*\s*%", ingredients, re.I):
        return "Trockenprodukt zum Kochen (Getreide/Reis ≥ 50 % als erste Zutat)"
    if re.search(r"schnetzel (?:fein|grob)|sojaschnetzel", name, re.I):
        return "Trockenprodukt (Sojaschnetzel)"
    return None


def parse_product(page_html: str, url: str) -> Product:
    ld = _jsonld_product(page_html, url)
    a = attributes(page_html)
    offer = ld.get("offers") or {}
    if isinstance(offer, list):
        offer = offer[0] if offer else {}
    price = _f(offer.get("price"))
    name = _html.unescape(ld.get("name") or "").strip()
    size = parse_size_g(a.get("Produktmenge - Nettofüllmenge") or "") or parse_size_g(name)
    nut, basis = {}, (a.get("Durchschnittliche Nährwertangaben je") or "").replace(" ", "")
    if basis in ("", "100g", "100ml"):  # EU declaration basis; the shop omits the 'je' row on most pages
        for label, key in NUT_ROWS.items():
            v = _f(a.get(label))
            if v is not None:
                nut[key] = v
    nut_check = atwater_check(nut)
    imgs = ld.get("image") or []
    imgs = [imgs] if isinstance(imgs, str) else imgs
    imgs = [i for i in imgs if "brandpersonality" not in i] or imgs
    brand = (ld.get("brand") or {}).get("name") if isinstance(ld.get("brand"), dict) else ld.get("brand")
    props = a.get("Produkteigenschaft") or ""
    return Product(
        source="myproduct", store=STORE, name=name, brand=(brand or a.get("Produzent") or "").strip() or None,
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None, size_g=size, nutrition_100g=nut,
        ean=valid_ean(a.get("EAN Code")), image_url=imgs[0] if imgs else None,
        producer=a.get("Herstellerangaben") or a.get("Produzent"),
        origin=a.get("Produzent Land"), category="Fertiggericht",
        source_url=ld.get("url") or url, source_id=ld.get("sku") or a.get("SKU"),
        extra={
            "producer_brand": a.get("Produzent"), "ingredients": a.get("Zutatenliste"),
            "allergens": a.get("Allergeninformation"), "storage": a.get("Lagerhinweis"),
            "best_before": a.get("Mindesthaltbarkeitsdatum"), "properties": props,
            "bio": bool(re.search(r"\bbio\b", props, re.I)) or None,
            "vegan": bool(re.search(r"vegan", props, re.I)) or None,
            "nutrition_label": a.get("Nährwertkennzeichnung"), "nutrition_basis": basis or "100 g (implizit, EU-Standard)",
            "nutrition_check": nut_check, "kj": _f(a.get("Brennwert in kJ")), "preparation": a.get("Gebrauchsanleitung / Tipp"),
            "packaging_material": a.get("Verpackungsmaterial"),
            "availability": (offer.get("availability") or "").split("/")[-1] or None,
            "ean_raw": a.get("EAN Code"), "images": imgs,
            "exclusion": exclusion(name, a.get("Zutatenliste")),
            "unit_size_g": unit_size_g(name), "pack_count": pack_count(name), "shipping_note": SHIPPING_NOTE, "operator": OPERATOR,
            "price_note": "Preis inkl. MwSt. lt. Produktseite (schema.org Offer), zzgl. Versand",
        },
    )


def is_ready_meal(p: Product) -> bool:
    return bool(p.name and p.price_eur and p.size_g and p.image_url and not p.extra.get("exclusion"))


def product(url_or_key: str) -> Product | None:
    u = url_or_key.strip()
    if not u.startswith("http"):
        u = f"{BASE}/{u.strip('/')}"
    try:
        return parse_product(_html_get(u), u)
    except Exception:
        return None


class MyProduct(Adapter):
    id = "myproduct"
    store = STORE
    homepage = BASE
    notes = (
        "Live: myproduct.at (Marktplatz regionaler AT-Produzenten, myProduct GmbH Zwettl) — Kategorie Fertiggerichte "
        "(dataLayer + Kachel-Links) → Produktseiten (JSON-LD Offer + Magento-Attributtabelle: EAN, Nettofüllmenge, "
        "Hersteller, Zutaten, Nährwerte je 100 g falls veröffentlicht); Versand 7,90 €/10 kg AT; polite 1 req/s"
    )
    delay = 1.0

    def fetch(self, category="ready-meals", limit=1000):
        out = []
        for it in category_items(delay=self.delay)[:limit]:
            if not it.get("url"):
                continue
            time.sleep(self.delay)
            p = product(it["url"])
            if p and is_ready_meal(p):
                out.append(p)
        return out

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for it in category_items(delay=self.delay):
            hay = f"{it['name']} {it.get('brand') or ''}".lower()
            if all(w in hay for w in words) and not exclusion(it["name"]):
                out.append(Product(source="myproduct", store=STORE, name=it["name"], brand=it.get("brand"),
                                   price_eur=it.get("price"), size_g=parse_size_g(it["name"]),
                                   source_url=it.get("url"), source_id=it.get("sku"), category="Fertiggericht"))
            if len(out) >= limit:
                break
        return out
