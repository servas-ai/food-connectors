"""MPreis webshop (www.mpreis.at/shop) — live connector.

Uses only robots-allowed public pages: the product sitemaps (/sitemap/products*/sitemap.xml),
category pages (/shop/c/...) and product pages (/shop/p/<slug>-<sku>), parsing the schema.org
Product JSON-LD each page publishes (sku, gtin, brand, image, category, price, availability).
/search/ is disallowed by robots.txt and is never requested.
"""
from __future__ import annotations
import html as _h, json, os, re, time, unicodedata
from ..http import get
from ..schema import Product, parse_size_g, looks_like_ready_meal
from .base import Adapter

BASE = "https://www.mpreis.at"
CACHE = os.path.expanduser("~/.cache/food-connectors/mpreis_sitemap.json")
READY_MEAL_CATEGORIES = [
    "/shop/c/lebensmittel/konserven-fertiggerichte-suppen/fertiggerichte-5812424",
    "/shop/c/lebensmittel/konserven-fertiggerichte-suppen/fertiggerichte/dosengerichte-13509525",
    "/shop/c/lebensmittel/konserven-fertiggerichte-suppen/fertiggerichte/fertigmenues-17927965",
    "/shop/c/lebensmittel/konserven-fertiggerichte-suppen/fertiggerichte/kartoffelgerichte-knoedel-9336400",
    "/shop/c/lebensmittel/tiefkuehl/fertiggerichte-24125257",
    "/shop/c/lebensmittel/tiefkuehl/pizza-baguette-26319064",  # added 2026-10-13T11
]
LD_RE = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)

def _html(url: str) -> str:
    return get(url, raw=True, headers={"Accept": "text/html"}).decode("utf-8", "replace")

def _norm(s: str) -> str:
    s = s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def sitemap_urls(max_age_h: float = 24) -> list[str]:
    if os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < max_age_h * 3600:
        return json.load(open(CACHE))
    idx = _html(BASE + "/sitemap.xml")
    out = []
    for sm in re.findall(r"<loc>([^<]*sitemap/products[^<]*)</loc>", idx):
        out += re.findall(r"<loc>([^<]+/shop/p/[^<]+)</loc>", _html(sm)); time.sleep(0.4)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True); json.dump(out, open(CACHE, "w"))
    return out

def category_urls(path: str) -> list[str]:
    return sorted({BASE + p for p in re.findall(r'(/shop/p/[a-z0-9-]+)', _html(BASE + path))})

def product(url: str) -> Product | None:
    h = _html(url)
    ld = None
    for m in LD_RE.finditer(h):
        try: d = json.loads(m.group(1))
        except Exception: continue
        if isinstance(d, dict) and d.get("@type") == "Product": ld = d; break
    if not ld: return None
    off = ld.get("offers") or {}
    if isinstance(off, list): off = off[0] if off else {}
    brand = ld.get("brand"); brand = brand.get("name") if isinstance(brand, dict) else brand
    imgs = ld.get("image") or []; img = imgs[0] if isinstance(imgs, list) and imgs else (imgs or None)
    w = re.search(r'c3-product__weight-info-text[^>]*>([^<]+)<', h)
    size = parse_size_g(w.group(1) if w else "") or parse_size_g(ld.get("name"))
    nut = {}
    # The Nährwerte tab may hold several blocks ("Nicht zubereitete Portion (125 g)", "Nicht zubereitet je 100 g",
    # "Zubereitet je 100 g"); only per-100 g values are valid nutrition_100g. Prefer the unprepared per-100 g block.
    blocks = [(_h.unescape(t).strip(), body) for t, body in re.findall(
        r'content-block-title[^>]*>([^<]*)</div>((?:(?!content-block-title).)*?)</table>', h, re.S) if "c3-table__column-value" in body]
    per100 = [(t, b) for t, b in blocks if re.search(r'(?:je|pro) 100 ?(?:g|ml)', t, re.I)]
    per100.sort(key=lambda tb: 0 if re.search(r'nicht zubereitet', tb[0], re.I) else 1)
    # blocks present but none per 100 g (portion only) -> leave nutrition empty rather than mislabel it
    src = per100[0][1] if per100 else ("" if blocks else h)
    for k, v in re.findall(r'<tr><td>(.*?)</td><td class="c3-table__column-value">(.*?)</td></tr>', src):
        k = _h.unescape(k).strip(" \xa0-").lower(); m = re.search(r"[\d.,]+", v)
        if not m: continue
        x = float(m.group(0).replace(",", "."))
        key = ("kcal" if "kcal" in k else "satfat" if "gesättigt" in k else "sugar" if "zucker" in k else
               "fat" if k == "fett" else "carbs" if k.startswith("kohlenhydrat") else "protein" if k.startswith("eiwei") else
               "salt" if k == "salz" else "fiber" if "ballast" in k else None)
        if key and key not in nut: nut[key] = x
    zt = re.search(r'Zutatenliste</[^>]+>\s*(?:<[^>]+>\s*)*([^<]{10,})', h)
    ingredients = _h.unescape(zt.group(1)).strip() if zt else None
    price = off.get("price")
    return Product(source="mpreis-shop", store="MPreis", name=ld.get("name") or "", brand=brand,
                   price_eur=float(price) if price is not None else None, size_g=size, nutrition_100g=nut,
                   unit_price_eur=round(float(price) / size * 1000, 2) if price and size else None, unit="kg" if price and size else None,
                   ean=(ld.get("gtin") or "").lstrip("0") or None, image_url=img,
                   category=ld.get("category"), source_url=off.get("url") or url, source_id=str(ld.get("sku") or ""),
                   extra={"availability": (off.get("availability") or "").rsplit("/", 1)[-1], "gtin": ld.get("gtin"), "ingredients": ingredients})

class MpreisShop(Adapter):
    id = "mpreis-shop"; store = "MPreis"; homepage = BASE + "/shop"; status = "live"
    notes = "Live: sitemap + category pages + product JSON-LD (price, GTIN, image, brand). /search/ not used (robots)."
    def search(self, q: str, limit: int = 50) -> list[Product]:
        toks = _norm(q).split()
        hits = [u for u in sitemap_urls() if all(t in _norm(u.rsplit("/", 1)[-1]) for t in toks)][:limit]
        out = []
        for u in hits:
            try:
                p = product(u)
                if p: out.append(p)
            except Exception: pass
            time.sleep(0.5)
        return out
    def fetch(self, category: str = "ready-meals", limit: int = 500) -> list[Product]:
        if category != "ready-meals": return self.search(category, limit)
        urls = []
        for c in READY_MEAL_CATEGORIES:
            urls += [u for u in category_urls(c) if u not in urls]; time.sleep(0.5)
        out = []
        for u in urls[:limit]:
            try:
                p = product(u)
                if p and ("Fertig" in (p.category or "") or looks_like_ready_meal(p.name, p.category)): out.append(p)
            except Exception: pass
            time.sleep(0.5)
        return out
