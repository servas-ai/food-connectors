"""fit2go.meals (fittogo.at) — frozen ready meals cooked in Austria, shipped nationwide (incl. Linz).

Source: the public Hydrogen/Oxygen shop pages the site itself serves:
  * sitemap ``https://fittogo.at/sitemap/products/1.xml`` (product URLs)
  * product page ``/products/<handle>`` — server-rendered HTML with
    Gesamt-Einwaage, pack nutrition (kcal / Protein / Carbs / Fett) and packshot.
``/products.json`` and collection ``*.json`` answer 404 on this Hydrogen storefront
(catalog stub said "no public API"); the HTML product pages and the product sitemap
are robots-allowed (Disallow only /cart /account /collections/*sort_by* /search/?*).
No login, no cookies. Individual meal prices are € 0,00 on the product page (sold via
6er/12er/18er Mix-&-Match boxes); the published 12er box price (9,99 €/Meal) is
exposed in ``extra.box_price_12`` and as ``price_eur`` with an explicit source note —
never invented beyond what the collection page prints.
Operator: Fit2go GmbH, Piccoloweg 4, 4055 Pucking, FN 615822x, UID ATU80022878.
"""
from __future__ import annotations
import html as _html, json, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://fittogo.at"
SITEMAP = BASE + "/sitemap/products/1.xml"
STORE = "Online: Fit2go"
BOX_RE = re.compile(
    r"(?:^|/)(?:\d+er-meal-box|fit2go-mix|vorteilspaket|fitness-klassiker|bestseller-box|"
    r"musterpaket|probierpaket|termin|chicken-box|verkostungstermin|box|paket)(?:$|[?#])",
    re.I,
)
# Published on https://fittogo.at/collections/12er-box (and FAQ): 10,49 / 9,99 / 9,49 € per meal.
BOX_PRICE_12 = 9.99
BOX_PRICE_NOTE = (
    "Einzelgericht im Shop 0,00 € (nur über Mix-&-Match-Box); "
    "price_eur = veröffentlichter 12er-Box-Preis 9,99 €/Meal "
    "(6er 10,49 €, 18er 9,49 €) lt. fittogo.at/collections/12er-box"
)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def product_urls(sitemap_xml: str | None = None) -> list[str]:
    """All individual meal product URLs from the public product sitemap (boxes filtered out)."""
    xml = sitemap_xml if sitemap_xml is not None else get(
        SITEMAP, raw=True, timeout=60, headers={"Accept": "application/xml,text/xml"}
    ).decode("utf-8", "replace")
    urls = [_html.unescape(u) for u in re.findall(r"<loc>([^<]+)</loc>", xml) if "/products/" in u]
    return [u for u in urls if not BOX_RE.search(u)]


def is_meal_url(url: str) -> bool:
    return "/products/" in url and not BOX_RE.search(url)


def handle_of(url: str) -> str | None:
    m = re.search(r"/products/([a-z0-9-]+)", url)
    return m.group(1) if m else None


def parse_product(h: str, url: str) -> Product:
    """Parse a fittogo.at product HTML page into a Product (pack nutrition → per 100 g)."""
    handle = handle_of(url) or ""
    title = None
    m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S | re.I)
    if m:
        title = _clean(m.group(1))
    if not title:
        m = re.search(r'og:title"\s+content="([^"]+)"', h)
        if m:
            title = _html.unescape(m.group(1)).split("–")[0].split("-")[0].strip()
    if not title:
        title = handle.replace("-", " ").title()

    # Visible body text (scripts stripped) carries Einwaage + pack macros.
    vis = re.sub(r"<script[^>]*>.*?</script>", " ", h, flags=re.S | re.I)
    vis = re.sub(r"<style[^>]*>.*?</style>", " ", vis, flags=re.S | re.I)
    vis = _clean(vis)

    size = None
    sm = re.search(r"Gesamt-Einwaage\s*(\d+)\s*[gG]", vis)
    if sm:
        size = float(sm.group(1))

    pack = {}
    nm = re.search(
        r"(\d+(?:[.,]\d+)?)\s*kcal\s+(\d+(?:[.,]\d+)?)\s*g\s*Protein\s+"
        r"(\d+(?:[.,]\d+)?)\s*g\s*Carbs\s+(\d+(?:[.,]\d+)?)\s*g\s*Fett",
        vis,
        re.I,
    )
    if nm:
        pack = {
            "kcal": float(nm.group(1).replace(",", ".")),
            "protein": float(nm.group(2).replace(",", ".")),
            "carbs": float(nm.group(3).replace(",", ".")),
            "fat": float(nm.group(4).replace(",", ".")),
        }
    else:
        # Fallback: heavily escaped React Flight payload ``meal_nutrients``.
        mm = re.search(
            r"meal_nutrients\\*",
            h,
        )
        # Match both raw and multi-escaped JSON forms
        jm = re.search(
            r'meal_nutrients\\*",\\*"(\{.*?\})\\*"',
            h,
        ) or re.search(
            r"meal_nutrients\\+\"?,\\+\"?(\{.*?CARBS.*?\})",
            h,
        )
        if jm:
            raw = jm.group(1)
            for _ in range(4):
                raw2 = raw.replace("\\\\", "\\").replace('\\"', '"')
                if raw2 == raw:
                    break
                raw = raw2
            try:
                d = json.loads(raw)
                pack = {
                    "kcal": float(d["KCAL"]),
                    "protein": float(d["PROTEIN"]),
                    "carbs": float(d["CARBS"]),
                    "fat": float(d["FETT"]),
                }
            except (ValueError, KeyError, TypeError):
                pass

    nut = {}
    if size and pack:
        f = 100.0 / size
        nut = {k: round(v * f, 1) for k, v in pack.items()}

    # Packshot: prefer the product's own CDN file referenced near the handle / first files/ image.
    image = None
    for pat in (
        r'og:image"\s+content="(https://cdn\.shopify\.com/[^"]+)"',
        r"(https://cdn\.shopify\.com/s/files/1/0580/7777/3988/files/[^\"\\?\s]+\.png(?:\?v=\d+)?)",
    ):
        im = re.search(pat, h)
        if im:
            image = _html.unescape(im.group(1)).split("&")[0]
            break

    ingredients = None
    im = re.search(r"Zutaten\s+(.+?)(?:Allergene|Unsere schockgefrosteten|Nährwerte|\Z)", vis, re.I | re.S)
    if im:
        ingredients = re.sub(r"\s+", " ", im.group(1)).strip()[:800] or None

    allergens = None
    am = re.search(r"Allergene:\s*([A-Z0-9,\s-]+)", vis)
    if am:
        allergens = am.group(1).strip(" -")

    veg = None
    if re.search(r"\bvegan", title + " " + (ingredients or ""), re.I):
        veg = True
    elif ingredients and re.search(
        r"huhn|hühn|hähnchen|pute|rind|schwein|fleisch|faschiert|schinken|"
        r"thunfisch|lachs|fisch|speck|wurst|gelatine",
        ingredients,
        re.I,
    ):
        veg = False

    return Product(
        source="fittogo",
        store=STORE,
        name=title,
        brand="fit2go.meals",
        price_eur=BOX_PRICE_12,
        unit_price_eur=round(BOX_PRICE_12 / size * 1000, 2) if size else None,
        unit="kg" if size else None,
        size_g=size,
        nutrition_100g=nut,
        ean=None,
        image_url=image,
        producer="Fit2go GmbH, Piccoloweg 4, 4055 Pucking (FN 615822x)",
        origin="Österreich",
        category="Online Meal-Prep",
        source_url=f"{BASE}/products/{handle}" if handle else url,
        source_id=handle,
        extra={
            "pack_nutrition": pack or None,
            "allergens": allergens,
            "ingredients": ingredients,
            "veg": veg,
            "shipping_eur": 4.99,
            "shipping_note": "österreichweit 4,99 € Express (Di–Do Versand) lt. fittogo.at",
            "box_price_6": 10.49,
            "box_price_12": BOX_PRICE_12,
            "box_price_18": 9.49,
            "price_note": BOX_PRICE_NOTE,
            "storage": "Tiefkühl (TK), schockgefrostet, 12 Monate",
            "prep": "7–10 Min Mikrowelle/Pfanne oder 40–45 Min Heißluftofen (lt. fittogo.at)",
        },
    )


def is_ready_meal(p: Product) -> bool:
    if not p.name or BOX_RE.search(p.source_url or ""):
        return False
    if not p.size_g or not p.nutrition_100g.get("protein"):
        return False
    # Drop pure desserts / ice if any slip through
    if re.search(r"\beis\b|gutschein|merch|shaker", p.name, re.I):
        return False
    return True


class FitToGo(Adapter):
    id = "fittogo"
    store = STORE
    homepage = BASE
    notes = (
        "Live: public product sitemap + product HTML (Hydrogen shop; /products.json 404). "
        "Pack nutrition + Einwaage from the rendered page; price_eur = published 12er-box 9,99 €/Meal "
        "(individual SKU price is 0,00 €). AT shipping 4,99 €. robots-allowed paths only, no login/cookies."
    )

    def fetch(self, category="ready-meals", limit=500):
        import time
        out = []
        for u in product_urls()[:limit]:
            try:
                h = get(u, raw=True, timeout=40).decode("utf-8", "replace")
            except Exception:
                continue
            p = parse_product(h, u)
            if is_ready_meal(p):
                out.append(p)
            time.sleep(1.0)
        return out[:limit]

    def search(self, q, limit=50):
        words = re.findall(r"\w{3,}", q.lower())
        # Search by slug first (cheap), then parse hits
        import time
        urls = product_urls()
        fold = lambda s: s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        hits = [u for u in urls if all(fold(w) in fold(u) for w in words)][: max(limit, 5)]
        out = []
        for u in hits:
            try:
                h = get(u, raw=True, timeout=40).decode("utf-8", "replace")
            except Exception:
                continue
            p = parse_product(h, u)
            if is_ready_meal(p):
                out.append(p)
            time.sleep(1.0)
            if len(out) >= limit:
                break
        return out[:limit]
