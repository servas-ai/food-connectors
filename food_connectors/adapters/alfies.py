"""Alfies (alfies.at) — Viennese online supermarket (60-min delivery in Wien, pre-order delivery in Graz).

Sources (public, no login/cookies; www.alfies.at robots.txt ``User-agent: * / Disallow:`` = everything
allowed; api.alfies.at has no robots.txt):
  * Product listing/search = the Algolia index the alfies.at shop front-end queries from every anonymous
    browser (app id + *search-only* public key shipped in the public ``/_next/static/chunks/pages/_app-*.js``
    bundle; read-only, cannot write or list indexes). Index ``products_<warehouse>_de_at``; warehouse
    ``altha`` = Wien (instant-shipping-one-hour), ``graz`` = Graz (preorder-shipping) — resolved by the
    shop's own ``POST www.alfies.at/api/get-warehouse {latitude, longitude}`` (Linz → no warehouse).
    Hit: id, slug, title, brand, displayUnit (pack), categories (path), images, per-warehouse price incl.
    MwSt., €/unit, deposit fee, stock.
  * Product detail = ``GET api.alfies.at/api/v1/catalogue/products-mm/<id>`` (the shop's own public
    catalogue API, no auth): attributes.nutrition (free-text table "pro 100 g …"), ingredients, brand,
    cross-retailer ids (billaId, gurkerlId, intersparId, unimarktId), weightNetKg.
Ready meals = products in category paths ``ready-to-eat`` ("Fix & Fertig") or ``frozen-ready-meals``
(Tiefgekühlte Fertiggerichte), minus doughs/baking mixes, pickled salads, desserts and meat snacks.
No GTIN on alfies.at → ean None (the hub may twin-fill from billaId/gurkerlId rows it already has).
Operator (alfies.at/impressum, VIES + GLEIF verified 2026-10-14): Alfie's GmbH, Mariahilfer Straße 37-39,
1060 Wien, FN 352065v (HG Wien), UID ATU68436258, LEI 984500B8Z9EOKFE27580.
Polite 1 req/s for detail calls.
"""
from __future__ import annotations
import html as _html, json, os, re, time, urllib.parse, urllib.request
from .base import Adapter
from ..http import get, UA
from ..schema import Product, parse_size_g

BASE = "https://www.alfies.at"
API = "https://api.alfies.at/api/v1"
STORE = "Alfies"
PRODUCER_OPERATOR = "Alfie's GmbH, Mariahilfer Straße 37-39, 1060 Wien, FN 352065v"
# Public search-only Algolia credentials embedded in the alfies.at front-end bundle (read-only).
ALGOLIA_APP = os.environ.get("ALFIES_ALGOLIA_APP", "RNJAZYGUWW")
ALGOLIA_KEY = os.environ.get("ALFIES_ALGOLIA_KEY", "06c83e9e39cd1595f93c545ea64f6348")
WAREHOUSES = {"altha": "Wien", "guthe": "Wien", "macu": "Wien", "graz": "Graz (Vorbestellung)"}  # via /api/get-warehouse probes 2026-10-14
DEFAULT_WH = "altha"
MEAL_PATHS = ("ready-to-eat", "frozen-ready-meals")
EXCLUDE_CATS = {"baking-mixes-doughs"}
NOT_MEAL = re.compile(
    r"teig\b|teig |tassenküchlein|backmischung|salat in|rote rüben|karottensalat|essiggurk|tiramisu|kuchen|torte|"
    r"\bbifi\b|carazza|kabanos|sauce\b|würzpaste|kartoffelsalat",
    re.I,
)
_NUM = r"(<\s*)?(\d+(?:[.,]\d+)?)"
NUT_RX = {
    "fat": r"(?<![a-zäöü])Fett(?![a-zäöü])(?![\s,:]*davon)",
    "satfat": r"ges[äa]e?t+igte\s*Fetts[äa]ure?n?",
    "carbs": r"Kohlenhydrate?(?![\s,:]*davon)",
    "sugar": r"(?<![a-zäöü])Zucker",
    "fiber": r"Ballaststoffe?",
    "protein": r"(?:Eiwei(?:ß|ss)|Protein)",
    "salt": r"(?<![a-zäöü])(?:Koch)?[Ss]alz(?:\s*Äquivalent)?",
}
# only separators may sit between a label and its value, so a missing value ("kA") never borrows the next row's number
_GAP = r"[\s:~\-–|()]*"


def _f(s):
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _plain(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.I)
    s = _html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t\xa0]+", " ", s.replace("\r", "")).strip()


def parse_nutrition(text: str | None) -> tuple[dict, dict]:
    """Free-text 'pro 100 g …' table → (per100, meta). meta: basis ('g'|'ml'), lt (keys given as '< x')."""
    t = _plain(text)
    if not t:
        return {}, {}
    m = re.search(r"pro\s*100\s*(g|gr|ml)\b", t, re.I)
    basis = "ml" if m and m.group(1).lower() == "ml" else "g"
    body = t[m.start():] if m else t
    body = re.split(r"Nährwertanspruch|pro Portion|je Portion", body, flags=re.I)[0]
    flat = re.sub(r"\s*\n\s*", " ", body)
    out, lt = {}, []
    k = re.search(r"(\d+(?:[.,]\d+)?)\s*kcal", flat, re.I)
    if k:
        out["kcal"] = _f(k.group(1))
    for key, rx in NUT_RX.items():
        mm = re.search(rx + _GAP + _NUM + r"\s*(?:g|gr)\b", flat, re.I)
        if mm:
            v = _f(mm.group(2))
            if v is not None:
                out[key] = v
                if mm.group(1):
                    lt.append(key)
    return out, {"basis": basis, "lt": lt}


def consistent(n: dict) -> bool:
    """Plausibility gate: macros ≤ 100 g and kcal within ±25 % (+15 kcal) of 4/4/9 (+2 fibre)."""
    p, c, f = n.get("protein"), n.get("carbs"), n.get("fat")
    if None in (p, c, f) or n.get("kcal") is None:
        return False
    if p + c + f > 100.5 or n["kcal"] > 900:
        return False
    est = 4 * p + 4 * c + 9 * f + 2 * (n.get("fiber") or 0)
    return abs(est - n["kcal"]) <= 0.25 * max(n["kcal"], est) + 15


def algolia(query: str = "", warehouse: str = DEFAULT_WH, page: int = 0, per_page: int = 500,
            facet_filters: list | None = None) -> dict:
    params = {"query": query, "hitsPerPage": str(per_page), "page": str(page)}
    if facet_filters:
        params["facetFilters"] = json.dumps(facet_filters)
    url = (f"https://{ALGOLIA_APP.lower()}-dsn.algolia.net/1/indexes/products_{warehouse}_de_at?"
           + urllib.parse.urlencode(params))
    return get(url, headers={"X-Algolia-Application-Id": ALGOLIA_APP, "X-Algolia-API-Key": ALGOLIA_KEY}, timeout=30)


def warehouse_for(lat: float, lon: float) -> str | None:
    """Ask the shop which warehouse serves a location (same call the address picker makes)."""
    req = urllib.request.Request(f"{BASE}/api/get-warehouse", data=json.dumps({"latitude": lat, "longitude": lon}).encode(),
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        w = json.load(r).get("warehouse") or {}
    return w.get("warehouse_code")


def _paths(hit: dict) -> set[str]:
    return {p.get("slug") for c in hit.get("categories") or [] for p in c.get("path") or []}


def _cats(hit: dict) -> list[str]:
    return [c.get("slug") for c in hit.get("categories") or []]


def is_meal_hit(hit: dict) -> bool:
    if hit.get("hiddenFromCustomers") or not hit.get("isPublic", True):
        return False
    meal_cats = [c.get("slug") for c in hit.get("categories") or []
                 if {p.get("slug") for p in c.get("path") or []} & set(MEAL_PATHS)]
    if not meal_cats or all(c in EXCLUDE_CATS for c in meal_cats):
        return False
    return not NOT_MEAL.search(hit.get("title") or "")


def meal_hits(warehouse: str = DEFAULT_WH) -> list[dict]:
    seen, out = set(), []
    for slug in MEAL_PATHS:
        page = 0
        while True:
            d = algolia("", warehouse, page, 500, [[f"categories.path.slug:{slug}"]])
            for h in d.get("hits") or []:
                if h["id"] not in seen and is_meal_hit(h):
                    seen.add(h["id"]); out.append(h)
            page += 1
            if page >= (d.get("nbPages") or 0):
                break
    return out


def detail(pid) -> dict:
    return get(f"{API}/catalogue/products-mm/{pid}", timeout=40)


def _brand(hit: dict, det: dict | None) -> str | None:
    b = ((det or {}).get("attributes") or {}).get("brand") or (hit.get("attributes") or {}).get("brand")
    return b.strip() if isinstance(b, str) and b.strip() else None


def clean_title(t: str) -> str:
    # internal sort prefixes like "000_?" / "001?_" leak into a few titles
    t = (t or "").strip()
    t = re.sub(r"^(?:\d{2,3}\s*[_?]+|[ÜüUu][Zz][_-]\s*Saison\s*_)\s*", "", t)  # "000_?", "04_", "ÜZ_Saison_"
    return t.strip()


def to_product(hit: dict, det: dict | None = None, warehouse: str = DEFAULT_WH) -> Product:
    d = det or hit
    attrs = (d.get("attributes") or {})
    whs = ((hit.get("whs") or {}).get(warehouse) or (d.get("whs") or {}).get(warehouse) or {})
    dp = whs.get("displayPrice") or {}
    price = dp.get("priceInclTax") if dp.get("priceInclTax") is not None else whs.get("price")
    disp = d.get("displayUnit") or hit.get("displayUnit") or ""
    size = parse_size_g(disp)
    if not size and d.get("weightNetKg"):
        size = round(float(d["weightNetKg"]) * 1000, 1)
    per100, meta = parse_nutrition(attrs.get("nutrition"))
    imgs = d.get("images") or hit.get("images") or []
    cats = _cats(hit)
    tk = "frozen-ready-meals" in _paths(hit) or "tiefgekühlt" in (d.get("title") or "").lower() or "frozen-pizza" in cats
    desc = _plain(d.get("description"))
    unit_price = dp.get("unitPriceInclTax")
    return Product(
        source="alfies",
        store=STORE,
        name=clean_title(d.get("title") or hit.get("title")),
        brand=_brand(hit, det),
        price_eur=round(float(price), 2) if price is not None else None,
        unit_price_eur=round(float(unit_price), 2) if unit_price else (round(price / size * 1000, 2) if price and size else None),
        unit=(hit.get("unit") or "kg") if (unit_price or (price and size)) else None,
        size_g=size,
        nutrition_100g=per100 if per100 else {},
        ean=None,
        image_url=imgs[0] if imgs else None,
        producer=None,
        origin=attrs.get("country") or None,
        category=next((c.get("name") for c in hit.get("categories") or []
                       if {p.get("slug") for p in c.get("path") or []} & set(MEAL_PATHS)), None),
        source_url=f"{BASE}/produkt/{d.get('slug') or hit.get('slug')}",
        source_id=str(d.get("id") or hit.get("id")),
        extra={
            "slug": d.get("slug") or hit.get("slug"),
            "display_unit": disp,
            "warehouse": warehouse,
            "warehouse_area": WAREHOUSES.get(warehouse),
            "available": ((whs.get("availability") or {}).get("hasAvailableStock")),
            "deposit_fee": dp.get("depositFee"),
            "category_slugs": cats,
            "frozen": bool(tk),
            "nutrition_basis": meta.get("basis"),
            "nutrition_lt": meta.get("lt") or [],
            "nutrition_consistent": consistent(per100) if per100 else None,
            "nutrition_raw": _plain(attrs.get("nutrition"))[:600] or None,
            "ingredients": _plain(attrs.get("ingredients")) or None,
            "preparation": desc or None,
            "billa_id": attrs.get("billaId") or None,
            "gurkerl_id": attrs.get("gurkerlId") or None,
            "interspar_id": attrs.get("intersparId") or None,
            "images": imgs,
            "operator": PRODUCER_OPERATOR,
            "delivery_note": "Lieferung nur Wien (60 Min, Warehouse altha) und Graz (Vorbestellung); Linz: kein Warehouse",
        },
    )


def product(id_or_slug_or_url: str, warehouse: str = DEFAULT_WH) -> Product | None:
    s = str(id_or_slug_or_url).strip().rstrip("/").split("?")[0].split("/")[-1]
    try:
        det = detail(s) if s.isdigit() else get(f"{API}/catalogue/products/slug-mm/{urllib.parse.quote(s)}", timeout=40)
    except Exception:
        return None
    if not det or not det.get("id"):
        return None
    hit = det
    try:  # price/stock per warehouse lives in the search index
        hs = algolia("", warehouse, 0, 1, [[f"id:{det['id']}"]]).get("hits") or []
        if hs:
            hit = hs[0]
    except Exception:
        pass
    return to_product(hit, det, warehouse)


def is_ready_meal(p: Product) -> bool:
    n = p.nutrition_100g
    return bool(p.name) and bool(p.price_eur) and n.get("kcal") is not None and n.get("protein") is not None


class Alfies(Adapter):
    id = "alfies"
    store = STORE
    homepage = BASE
    notes = (
        "Live: Viennese online supermarket (Wien 60-min, Graz pre-order; no Linz delivery). Listing via the "
        "public search-only Algolia index the shop front-end uses (products_<warehouse>_de_at, ready-to-eat + "
        "frozen-ready-meals paths) + public catalogue API api.alfies.at/api/v1/catalogue/products-mm/<id> "
        "(nutrition text per 100 g, ingredients, cross-retailer ids). Price incl. MwSt. per warehouse, "
        "packshots static.alfies.at; no GTIN; polite 1 req/s"
    )
    delay = 1.0

    def fetch(self, category="ready-meals", limit=1000, warehouse=DEFAULT_WH):
        out = []
        for h in meal_hits(warehouse)[:limit]:
            time.sleep(self.delay)
            try:
                det = detail(h["id"])
            except Exception:
                det = None
            out.append(to_product(h, det, warehouse))
        return out

    def search(self, q, limit=50, warehouse=DEFAULT_WH):
        d = algolia(q, warehouse, 0, min(max(limit * 3, 20), 200))
        out = []
        for h in (d.get("hits") or []):
            if not is_meal_hit(h):
                continue
            time.sleep(self.delay)
            try:
                det = detail(h["id"])
            except Exception:
                det = None
            out.append(to_product(h, det, warehouse))
            if len(out) >= limit:
                break
        return out
