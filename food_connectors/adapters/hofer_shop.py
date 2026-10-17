"""HOFER Österreich — live connector for the public hofer.at product catalogue (ALDI SÜD Nuxt shop front).

Access path (no login, no cookies, no browser, no JS execution):
  sitemap  https://www.hofer.at/sitemap_products.xml           (≈1300 product URLs, 2026-10-17)
  product  https://www.hofer.at/produkt/<slug>-<18-digit sku>  (server-rendered; the page's own __NUXT_DATA__
           payload + schema.org JSON-LD Product/Offer)
robots.txt (checked 2026-10-17): ``User-agent: *`` disallows only /tools and /*?q= (search) — the sitemaps and
/produkt/ pages are allowed; this adapter never calls the search endpoint. Requests go through the food-connectors
polite gate (robots.txt enforced, ≥1 s per host). Until 2026-10-16 hofer.at answered bots with Akamai 403; the
adapter does not retry or work around a 403 — it raises.
Per product: name, brand, regular shelf price (price.amount, cents), €/kg or €/l (price.comparison), selling size,
'Verfügbar seit' date, ingredients, storage/usage instructions, allergens, discontinued flag, official packshot
(dm.emea.cms.aldi.cx Scene7, width templated). hofer.at publishes NO GTIN and NO nutrition table → those fields stay
empty (never estimated; use `off` only by exact EAN from the pack).
"""
from __future__ import annotations
import json, re, unicodedata
from .base import Adapter
from ..http import get
from ..schema import Product, parse_size_g, looks_like_ready_meal

BASE = "https://www.hofer.at"
SITEMAP = BASE + "/sitemap_products.xml"
PRODUCT_RE = re.compile(r"/produkt/([a-z0-9-]+?)-(\d{18})/?$")
# slug prefilter for fetch(): only these product pages are opened (keeps the crawl small and polite)
MEAL_WORDS = ("lasagne", "gulasch", "curry", "chili", "eintopf", "suppe", "risotto", "bowl", "pizza", "flammkuchen",
              "nudel", "noodle", "ramen", "pasta", "tortellini", "ravioli", "gnocchi", "spaetzle", "knoedel", "fleckerl",
              "pfanne", "reis", "fischstaebchen", "backfisch", "schnitzel", "cevapcici", "burger", "hot-dog", "topf",
              "menue", "gericht", "kebab", "burrito", "wrap", "frikassee", "geschnetzeltes", "auflauf", "moussaka",
              "paella", "nasi", "bami", "tikka", "dal", "linsen", "bohnen", "erbsen", "ripperl", "braten", "strudel")
HOFER_MEAL_RE = re.compile(r"pizza|flammkuchen|fischstäbchen|backfisch|noodles? cup|nudelschüssel|pilztopf|hot dog|"
                           r"lasagne|knödel|thunfisch-reis|burrito|kebab|auflauf", re.I)
NOT_MEAL_RE = re.compile(r"sauce|soße|\bfix\b|gewürz|würzmittel|würzpaste|\bpaste\b|brühe|bouillon|aufstrich|pesto|backmischung|"
                         r"\bmehl\b|pizzateig|pizzakäse|teigblätter|chips|riegel|dessert|tierfutter|hundefutter|katzenfutter|instant|"
                         # raw meat / raw sides / bakery / non-food that share dish words in the slug
                         r"schnitzel|filet|würfel|geschnetzeltes|cevapcici|burgerscheiben|brötchen|\broll\b|\bbun\b|"
                         r"hülsenfr|bohnen|kichererbsen|\blinsen\b|\bpasta\b|linguine|\bnudeln\b|pfannengemüse|aufschnitt|"
                         r"thunfisch mix|bratpfanne|backbox|brunch|kornvariation|schoko", re.I)

def sitemap_urls() -> list[str]:
    x = get(SITEMAP, raw=True, timeout=40).decode("utf-8", "replace")
    return [u for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", x) if PRODUCT_RE.search(u)]

def _devalue(n: list, i: int, depth: int = 0):
    """Resolve Nuxt 3 devalue payload (array of nodes, ints are references)."""
    if depth > 40: return None
    x = n[i]
    if isinstance(x, dict): return {k: _devalue(n, v, depth + 1) if isinstance(v, int) else v for k, v in x.items()}
    if isinstance(x, list):
        if x and isinstance(x[0], str) and x[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"):
            return _devalue(n, x[1], depth + 1) if len(x) > 1 and isinstance(x[1], int) else None
        if x and isinstance(x[0], str) and x[0] in ("Set", "Map", "Date", "BigInt", "RegExp", "null", "undefined", "NaN"):
            return x[1] if len(x) > 1 else None
        return [_devalue(n, v, depth + 1) if isinstance(v, int) else v for v in x]
    return x

def parse_page(html: str, url: str | None = None) -> dict | None:
    """Return the resolved product node of a hofer.at /produkt/ page (or None)."""
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m: return None
    n = json.loads(m.group(1))
    sku = (PRODUCT_RE.search(url or "") or [None, None, None])[2] if url else None
    for i, x in enumerate(n):
        if isinstance(x, dict) and "sku" in x and "sellingSize" in x and "price" in x:
            p = _devalue(n, i)
            if not sku or p.get("sku") == sku: return p
    return None

def image_url(p: dict, width: int = 600) -> str | None:
    for a in p.get("assets") or []:
        u = a.get("url") or ""
        if u and (a.get("assetType") or "").startswith("FR"):
            return u.replace("{width}", str(width)).replace("{slug}", p.get("urlSlugText") or "produkt")
    a = (p.get("assets") or [{}])[0].get("url")
    return a.replace("{width}", str(width)).replace("{slug}", p.get("urlSlugText") or "produkt") if a else None

def to_product(p: dict, url: str | None = None) -> Product:
    pr = p.get("price") or {}
    # random-weight articles (e.g. 'ungefähr 0,5 kg/Stück'): amount = €/kg, amountRelevant = price of one piece
    amt = pr.get("amountRelevant") if isinstance(pr.get("amountRelevant"), (int, float)) else pr.get("amount")
    cmp_ = pr.get("comparison")
    unit = None
    m = re.search(r"/\s*1\s*(kg|l)\b", pr.get("comparisonDisplay") or "", re.I)
    if m: unit = m.group(1).lower()
    brand = _nfc(p.get("brandName")).strip() or None  # hofer.at ships some names NFD-decomposed
    name = _nfc(p.get("name")).strip()
    full = f"{brand.title() if brand and brand.isupper() else brand} {name}".strip() if brand else name
    cats = [c.get("name") for c in (p.get("categories") or []) if isinstance(c, dict) and c.get("name")]
    return Product(source="hofer-shop", store="HOFER", name=full, brand=brand,
        price_eur=amt / 100 if isinstance(amt, (int, float)) else None,
        unit_price_eur=cmp_ / 100 if isinstance(cmp_, (int, float)) else None, unit=unit,
        size_g=parse_size_g(p.get("sellingSize")), ean=None, image_url=image_url(p), category=" | ".join(cats) or None,
        source_url=url or f"{BASE}/produkt/{p.get('canonical')}", source_id=p.get("sku"),
        extra={"selling_size": p.get("sellingSize"), "ingredients": _nfc(p.get("ingredients")) or None,
               "storage": p.get("storageInstructions"), "usage": p.get("usageInstructions"),
               "allergens": p.get("allergens") or [], "on_sale_date": p.get("onSaleDate"),
               "on_sale_display": p.get("onSaleDateDisplay"), "discontinued": bool(p.get("discontinued")),
               "not_for_sale_online": bool(p.get("notForSale")), "price_display": pr.get("amountRelevantDisplay"),
               "comparison_display": pr.get("comparisonDisplay"), "was_price_display": pr.get("wasPriceDisplay"),
               "country_origin": p.get("countryOrigin"), "abstract_sku": p.get("abstractSku"),
               "nutrition_note": "hofer.at veröffentlicht keine Nährwerte/EAN — nicht geschätzt",
               "weight_article": bool(p.get("isRandomWeight")) or str(p.get("weightType") or "0") != "0",
               "price_basis": "price.amountRelevant = Regalpreis je Packung/Stück lt. hofer.at Produktseite (Filialpreis, kein Onlineshop); unit_price_eur = price.comparison"})

def product(url_or_sku: str) -> Product | None:
    """Exact lookup by hofer.at product URL, or by 18-digit sku (resolved via the product sitemap)."""
    s = url_or_sku.strip()
    if not s.startswith("http"):
        sku = s.zfill(18)
        s = next((u for u in sitemap_urls() if u.endswith("-" + sku)), None)
        if not s: return None
    try: h = get(s, raw=True, timeout=40).decode("utf-8", "replace")
    except Exception as e:
        if getattr(e, "code", None) in (404, 410): return None
        raise
    p = parse_page(h, s)
    return to_product(p, s) if p else None

def slug_candidate(url: str) -> bool:
    m = PRODUCT_RE.search(url); slug = m.group(1) if m else url
    return any(w in slug for w in MEAL_WORDS)

def _nfc(s: str | None) -> str:
    return unicodedata.normalize("NFC", s or "")

RAW_RE = re.compile(r"rohes fleisch|roher fisch|vor dem verzehr (gut )?durch(erhitzen|garen)|^100\s*% \w*fleisch", re.I)

def is_ready_meal(p: Product) -> bool:
    t = _nfc(p.name)
    if NOT_MEAL_RE.search(t): return False
    ex = p.extra or {}
    if RAW_RE.search(f"{ex.get('usage') or ''} {ex.get('ingredients') or ''}".strip()): return False  # raw meat/fish, not a dish
    return bool(HOFER_MEAL_RE.search(t)) or looks_like_ready_meal(t, p.category)

class HoferShop(Adapter):
    id = "hofer-shop"; store = "HOFER"; homepage = BASE; status = "live"
    notes = ("Live: hofer.at public product sitemap + server-rendered product pages (__NUXT_DATA__ / JSON-LD; robots allow, "
             "search /*?q= disallowed and not used; polite 1 req/s). Regular shelf price, €/kg, size, 'Verfügbar seit', "
             "ingredients, allergens, official packshot. No GTIN/nutrition published. fetch = slug prefilter → page → meal filter.")
    def search(self, q: str, limit: int = 10) -> list[Product]:
        words = [w for w in re.findall(r"[a-z0-9]{3,}", q.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))]
        urls = [u for u in sitemap_urls() if all(w in u for w in words)][:limit]
        return [p for p in (product(u) for u in urls) if p]
    def fetch(self, category: str = "ready-meals", limit: int = 60) -> list[Product]:
        urls = sitemap_urls()
        if category == "ready-meals": urls = [u for u in urls if slug_candidate(u)]
        elif category != "all": urls = [u for u in urls if category.lower() in u]
        out = []
        for u in urls:
            p = product(u)
            if p and (category != "ready-meals" or is_ready_meal(p)): out.append(p)
            if len(out) >= limit: break
        return out
