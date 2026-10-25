"""bofrost* Austria (bofrost.at) — frozen-food home delivery across Austria (own drivers, 14 Niederlassungen;
nearest to Linz: Sattledt, OÖ).

Source: the public bofrost.at shop pages the site itself serves:
  * sitemap index ``https://www.bofrost.at/sitemap.xml`` → PRODUCT-de-AT-EUR-*.xml (all product URLs)
  * product page ``/shop/<cat>_<id>/<subcat>_<id>/<slug>_<article>.html`` with schema.org JSON-LD Product
    (name, article no. = mpn, offers.price, availability, images), the pack line
    ("2 x 300 g = 600 g (1 kg = € 23,32)"), the nutrition table per 100 g, ingredients, portion size.
robots.txt (User-agent: *) disallows only /cart /checkout /account /shop/ajax/ /crm — none of these are used.
No login, no cookies, no search endpoint. bofrost publishes no GTIN/EAN on the page → ``ean`` stays None.
Operator: bofrost* Austria GmbH, 6430 Ötztal-Bahnhof, FN 185873v (LG Innsbruck), UID ATU66058936 (public Impressum).
"""
from __future__ import annotations
import html as _html, json, re, time
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.bofrost.at"
SITEMAP = BASE + "/sitemap.xml"
STORE = "Online: bofrost*"
# category slugs (first or second path segment) that hold ready meals / soups / pizza / prepared dishes
MEAL_CATS = ("pfannengerichte", "pasta_", "schlemmer-menues", "hausmannskost-suppen", "gerichte_", "suppen-suppeneinlagen",
             "laenderkueche", "pizza_", "gefluegelzubereitungen", "fleischzubereitungen", "vegetarisch", "vegan_",
             "bofrost-low-carb", "fuer-kleine-geniesser", "knoedel")
NOT_MEAL_RE = re.compile(r"\beis\b|eiskonfekt|\btorten?\b|kuchen|waffel|(?<!fleisch)(?<!gemüse)(?<!spinat)(?<!kraut)strudel|dessert|mousse|sorbet|"
                         r"\bwein\b|likör|gemüse natur|^kräuter|pommes|^rösti\b|kroketten|\bbeilage|suppengemüse", re.I)
PLAIN_SIDE_RE = re.compile(r"^(spätzle|semmelknödel|kartoffelknödel|gnocchi|nockerl)$", re.I)
SOUP_RE = re.compile(r"suppe|eintopf|topf\b", re.I)
_NUM = r"(\d+(?:[.,]\d+)?)"

def _f(s): return float(s.replace(".", "").replace(",", ".")) if s and "," in s else (float(s) if s else None)

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def _xml(url: str) -> str:
    return get(url, raw=True, timeout=60, headers={"Accept": "application/xml,text/xml"}).decode("utf-8", "replace")

def product_urls(index_xml: str | None = None, product_xml: str | None = None) -> list[str]:
    """All product URLs from the public PRODUCT sitemap."""
    if product_xml is None:
        idx = index_xml or _xml(SITEMAP)
        sm = next(_html.unescape(u) for u in re.findall(r"<loc>([^<]+)</loc>", idx) if "/PRODUCT-de-AT" in u)
        product_xml = _xml(sm)
    return [_html.unescape(u) for u in re.findall(r"<loc>([^<]+)</loc>", product_xml) if "/shop/" in u and u.endswith(".html")]

def article_no(url: str) -> str | None:
    m = re.search(r"_(\d{4,6})\.html$", url); return m.group(1) if m else None

MAYBE_CATS = ("neuheiten", "angebote", "nur-fuer-kurze-zeit", "faschierte-spezialitaeten", "meeresfruechte_", "beilagen_40882", "bio_")
DISH_SLUG_RE = re.compile(r"pfanne|sauce|suppe|curry|topf|roulade|strudel|auflauf|moussaka|cacciucco|tondelle|tortell|lasagne|"
                          r"maultaschen|eintopf|gulasch|ragout|risotto|paella|gratin|braten|schlemmerfilet", re.I)
EXCL_CATS_RE = re.compile(r"(^|/)eis_|suesse-vielfalt|gemuese_|kartoffelprodukte|wein-spirituosen|brot-gebaeck|obst_|kuechenhelfer|confiserie")

def is_meal_url(url: str) -> bool:
    """Category-path based pre-filter (the slug itself never decides exclusion: 'schweinsbraten' contains 'wein')."""
    parts = url.split("/shop/", 1)[-1].lower().split("/")
    cat, slug = "/".join(parts[:-1]), parts[-1]
    if EXCL_CATS_RE.search(cat): return False
    if any(c in cat for c in MEAL_CATS) and "beilagen_40882" not in cat: return True
    if not cat or any(c in cat for c in MAYBE_CATS): return bool(DISH_SLUG_RE.search(slug))
    return False

def _row(h: str, label_re: str) -> str | None:
    m = re.search(r"data-th='Nährwertangaben'>\s*" + label_re + r".*?data-th='Pro 100 (?:g|ml)[^']*'>\s*([^<]+)<", h, re.S | re.I)
    return _clean(m.group(1)) if m else None

def parse_product(h: str, url: str) -> Product:
    ld = {}
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try: d = json.loads(m.group(1).strip())
        except ValueError: continue
        if d.get("@type") == "Product": ld = d; break
    offer = ld.get("offers") or {}
    price = float(offer["price"]) if offer.get("price") not in (None, "") else None
    gm = re.search(r'product-grammage"[^>]*>(.*?)</div>', h, re.S)
    grammage = _clean(gm.group(1)) if gm else None
    size = None; unit_price = None
    if grammage:
        m = re.search(r"=\s*" + _NUM + r"\s*(kg|g|ml|l)\b", grammage) or re.search(r"^\s*" + _NUM + r"\s*(kg|g|ml|l)\b", grammage)
        if m: size = round(_f(m.group(1)) * (1000 if m.group(2) in ("kg", "l") else 1), 1)
        m = re.search(r"1\s*(kg|l)\s*=\s*€\s*" + _NUM, grammage)
        if m: unit_price = _f(m.group(2))
    pm = re.search(r"data-th='(Pro 100 (?:g|ml)[^']*)'", h)
    per = pm.group(1)[4:] if pm else None
    ns = re.search(r'alt="Nutri-Score ([A-E])"', h)
    n = {}
    e = _row(h, r"Brennwert")
    if e and (m := re.search(_NUM + r"\s*kcal", e)): n["kcal"] = _f(m.group(1))
    for key, lab in (("fat", r"Fett"), ("carbs", r"Kohlenhydrate"), ("fiber", r"Ballaststoffe"), ("protein", r"Eiweiß"), ("salt", r"Salz")):
        v = _row(h, lab)
        if v and (m := re.match(r"<?\s*" + _NUM + r"\s*g(?:\s*\(\s*<?\s*" + _NUM + r"\s*g\s*\))?", v)):
            n[key] = _f(m.group(1))
            if m.group(2) is not None: n["satfat" if key == "fat" else "sugar"] = _f(m.group(2))
    ing = re.search(r'id="pds-tab-ingredients"[^>]*>(.*?)(?:Zubereitung</|<h4>|</div>)', h, re.S)
    ingredients = _clean(ing.group(1)) if ing else None
    portion = re.search(r"Portionsgröße:\s*([^<]+)<", h)
    portions = re.search(r"Anzahl Portionen pro Packung:\s*" + _NUM, h)
    dl = re.search(r'"dimension1":(\[[^\]]*\])', h)
    cats = json.loads(dl.group(1)) if dl else []
    imgs = ld.get("image") or []
    return Product(source="bofrost", store=STORE, name=(ld.get("name") or "").strip(), brand="bofrost*",
                   price_eur=price, unit_price_eur=unit_price, unit="kg" if unit_price else None, size_g=size,
                   nutrition_100g=n, ean=None, image_url=imgs[0] if imgs else None,
                   producer="bofrost* Austria GmbH (Vertrieb), Ötztal-Bahnhof", category=" > ".join(cats) or None,
                   source_url=url, source_id=ld.get("mpn") or article_no(url),
                   extra={"grammage": grammage, "availability": (offer.get("availability") or "").rsplit("/", 1)[-1] or None,
                          "nutrition_per": per, "nutriscore": ns.group(1) if ns else None, "ingredients": ingredients, "description": ld.get("description"),
                          "portion": _clean(portion.group(1)) if portion else None,
                          "portions": _f(portions.group(1)) if portions else None, "categories": cats,
                          "price_note": "Preis inkl. MwSt. lt. öffentlicher Produktseite; kein GTIN öffentlich"})

def product(url_or_article: str, urls: list[str] | None = None) -> Product | None:
    url = url_or_article
    if not url.startswith("http"):
        no = url_or_article.zfill(5)
        url = next((u for u in (urls or product_urls()) if article_no(u) == no), None)
        if not url: return None
    try: h = get(url, raw=True, timeout=40).decode("utf-8", "replace")
    except Exception as e:
        if getattr(e, "code", None) == 404: return None
        raise
    p = parse_product(h, url)
    return p if p.name else None

# warm Mehlspeisen / Nachspeisen (heat-up desserts: Knödel, Schmarrn, Nockerl, Mohnnudeln, Strudel, Palatschinken) and
# warm starters (Frühlingsrollen, Teigtaschen, Flammkuchen, gefüllte Palatschinken, Kaspressknödel) — opt-in via
# ``fetch(category="desserts")`` / ``fetch(category="starters")``; cakes, Torten, Eis, Plunder, raw dough stay excluded.
DESSERT_CAT = "suessspeisen-desserts"
WARM_DESSERT_RE = re.compile(r"knoedel|schmarrn|nockerl|nudeln|strudel|palatschinken|apfelringe|germ", re.I)
NOT_WARM_DESSERT_RE = re.compile(r"blaetterteig|kaffeestuecke|torte|schnitten|eis", re.I)
# 2026-10-16T19: + Pizzettis, Rösti-Baguette, Gemüse-/Broccoli-Laibchen, Schinken-Käse-Röllchen (warm baked snacks; breaded cheese stays out)
STARTER_RE = re.compile(r"fruehlingsrollen|teigtaschen|flammkuchen|palatschinken-schinken|kaspressknoedel|pizzettis|roesti-baguette|"
                        r"gemueselaibchen|broccoli-laibchen|schinken-kaese-roellchen", re.I)

def is_warm_dessert_url(url: str) -> bool:
    cat, _, slug = url.split("/shop/", 1)[-1].lower().rpartition("/")
    return DESSERT_CAT in cat and bool(WARM_DESSERT_RE.search(slug)) and not NOT_WARM_DESSERT_RE.search(slug)

def is_starter_url(url: str) -> bool:
    cat, _, slug = url.split("/shop/", 1)[-1].lower().rpartition("/")
    return ("snacks_" in cat or "suppen-suppeneinlagen" in cat) and bool(STARTER_RE.search(slug))

def is_ready_meal(p: Product) -> bool:
    """Finished dishes only: no desserts/ice/sides, no plain Knödel/Spätzle, no soup garnishes (Suppeneinlagen)."""
    if not p.name or NOT_MEAL_RE.search(p.name) or PLAIN_SIDE_RE.match(p.name.strip()): return False
    if "Suppeneinlagen" in (p.category or "") and not SOUP_RE.search(p.name): return False
    return True

# --- GTIN via Open Food Facts (bofrost.at pages publish no GTIN; pack barcodes embed the article no.) ---
OFF_CODE_RE = re.compile(r"^0\d{4}69(\d{5})\d$")

def _gs1_ok(c: str) -> bool:
    if not c or not c.isdigit() or len(c) not in (8, 12, 13, 14): return False
    d = [int(x) for x in c]
    s = sum(v * (3 if i % 2 == 0 else 1) for i, v in enumerate(reversed(d[:-1])))
    return (10 - s % 10) % 10 == d[-1]

def barcode_article(code: str) -> str | None:
    """bofrost pack EAN-13 layout 0PPPP69AAAAAC: returns the 5-digit article no. AAAAA (GS1-valid codes only)."""
    m = OFF_CODE_RE.match(code or "")
    return m.group(1) if m and _gs1_ok(code) else None

def _off_qty_g(o: dict) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g)\b", (o.get("quantity") or "").lower())
    if not m: return None
    v = m.group(1)
    v = float(v.replace(".", "")) if re.fullmatch(r"\d{1,3}\.\d{3}", v) else float(v.replace(",", "."))
    return v * 1000 if m.group(2) == "kg" else v

_OFF_N = {"kcal": "energy-kcal_100g", "protein": "proteins_100g", "fat": "fat_100g", "carbs": "carbohydrates_100g"}

def off_gtin(p: Product, off_products: list[dict], tol: float = 0.05) -> str | None:
    """Pick the OFF code for this bofrost product: article no. in the barcode == p.source_id, net weight equal,
    kcal/protein/fat/carbs per 100 g within ±tol where OFF publishes them. Returns None if 0 or >1 candidates."""
    art = p.source_id or article_no(p.source_url or "")
    hits = []
    for o in off_products:
        c = str(o.get("code") or "")
        if barcode_article(c) != art: continue
        q = _off_qty_g(o)
        if not p.size_g or q is None or abs(q - p.size_g) > 0.5: continue
        n, ok = o.get("nutriments") or {}, True
        for k, ok_key in _OFF_N.items():
            a, b = (p.nutrition_100g or {}).get(k), n.get(ok_key)
            if a is None or b is None: continue
            if abs(float(a) - float(b)) > max(tol * max(float(a), float(b)), 0.3 if k != "kcal" else 2): ok = False
        if ok: hits.append(c)
    return hits[0] if len(set(hits)) == 1 else None

class Bofrost(Adapter):
    id = "bofrost"; store = STORE; homepage = BASE
    notes = ("Live: public sitemap + product pages (schema.org JSON-LD price/availability/images, pack line with €/kg, "
             "nutrition per 100 g, ingredients); frozen home delivery across AT (own drivers); no GTIN on bofrost.at — "
             "off_gtin() matches OFF pack barcodes (article no. embedded, 0PPPP69AAAAAC) by weight+nutrition; polite 1 req/s")
    delay = 1.0
    def fetch(self, category="ready-meals", limit=500):
        """category: "ready-meals" (default), "desserts" (warm Mehlspeisen) or "starters" (warm Vorspeisen/Snacks)."""
        sel = {"desserts": is_warm_dessert_url, "starters": is_starter_url}.get(category, is_meal_url)
        urls = [u for u in product_urls() if sel(u)]
        out = []
        for u in urls:
            p = product(u, urls)
            time.sleep(self.delay)
            if p and (sel is not is_meal_url or is_ready_meal(p)):
                p.extra["course"] = {"desserts": "dessert", "starters": "vorspeise"}.get(category, "haupt")
                out.append(p)
            if len(out) >= limit: break
        return out
    def search(self, q, limit=50):
        words = [w for w in re.findall(r"\w{3,}", q.lower())]
        urls = product_urls()
        fold = lambda s: s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        hits = [u for u in urls if all(fold(w) in fold(u) for w in words)][:limit]
        out = []
        for u in hits:
            p = product(u, urls); time.sleep(self.delay)
            if p: out.append(p)
        return out
