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
                          r"maultaschen|eintopf|gulasch|ragout|risotto|paella|gratin|braten", re.I)
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

def is_ready_meal(p: Product) -> bool:
    """Finished dishes only: no desserts/ice/sides, no plain Knödel/Spätzle, no soup garnishes (Suppeneinlagen)."""
    if not p.name or NOT_MEAL_RE.search(p.name) or PLAIN_SIDE_RE.match(p.name.strip()): return False
    if "Suppeneinlagen" in (p.category or "") and not SOUP_RE.search(p.name): return False
    return True

class Bofrost(Adapter):
    id = "bofrost"; store = STORE; homepage = BASE
    notes = ("Live: public sitemap + product pages (schema.org JSON-LD price/availability/images, pack line with €/kg, "
             "nutrition per 100 g, ingredients); frozen home delivery across AT (own drivers); no GTIN; polite 1 req/s")
    delay = 1.0
    def fetch(self, category="ready-meals", limit=500):
        urls = [u for u in product_urls() if is_meal_url(u)]
        out = []
        for u in urls:
            p = product(u, urls)
            time.sleep(self.delay)
            if p and is_ready_meal(p): out.append(p)
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
