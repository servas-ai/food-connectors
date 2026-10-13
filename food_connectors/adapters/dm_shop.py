"""dm drogerie markt Österreich — live connector (no login, no cookies, no browser).

Access path (robots-allowed only; dm.at /search is disallowed and never requested):
  1. https://www.dm.at/product-sitemap.xml  -> product URLs with their DAN (dm article number)
  2. https://products.dm.de/product/products/detail/AT/dan/{dan} -> the public JSON the dm.at product
     page renders: brand, title, GTIN, live price, breadcrumbs, nutrition table, ingredients, origin, images.
Ready meals = dm breadcrumb "Ernährung > Fertiggerichte & Konserven" (plain "Konserven" and sauces excluded).
AI-generated images (isAiGenerated) are never returned.
"""
from __future__ import annotations
import json, os, re, time
from ..http import get
from ..schema import Product
from .base import Adapter

SITEMAP = "https://www.dm.at/product-sitemap.xml"
API = "https://products.dm.de/product/products/detail/AT/dan/{dan}"
CACHE = os.path.expanduser("~/.cache/food-connectors/dm_sitemap.json")
SLUG = re.compile(r"fertiggericht|eintopf|suppe|bowl|ravioli|gulasch|curry|chili|dal\b|lasagne|nudel-tasse|baked-beans|risotto")
SLUG_NOT = re.compile(r"gewuerz|tee-|sauce-|paste|katze|hund|shampoo|duft|kerze|pulver|baby|kinder|kids|ab-\d|monat|smoothie|cups|aufstrich|riegel|reis-|risottoreis|lipgloss|nagellack|chips|waffeln|cashew|knabber|pesto|mariniert|nudeln-")
DROP_NAME = re.compile(r"bolognese|topping", re.I)

def _num(s):
    m = re.search(r"(\d+(?:[.,]\d+)?)", s or ""); return float(m.group(1).replace(",", ".")) if m else None

def sitemap_urls(max_age_h: float = 24) -> list[str]:
    if os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < max_age_h * 3600:
        return json.load(open(CACHE))
    xml = get(SITEMAP, raw=True, headers={"Accept": "application/xml"}).decode("utf-8", "replace")
    out = sorted(set(re.findall(r"https://www\.dm\.at/p/d/\d+/[a-z0-9-]+", xml)))
    os.makedirs(os.path.dirname(CACHE), exist_ok=True); json.dump(out, open(CACHE, "w"))
    return out

def _group(d, header):
    for g in d.get("descriptionGroups") or []:
        if g.get("header") == header: return g.get("contentBlock") or []
    return []

def _texts(d, header):
    return " ".join(t for b in _group(d, header) for t in (b.get("texts") or [])).strip() or None

def parse_nutrition(d: dict) -> tuple[dict, str | None]:
    out, basis = {}, None
    keymap = [("gesättigte", "satfat"), ("zucker", "sugar"), ("ballast", "fiber"), ("fett", "fat"),
              ("kohlenhydrate", "carbs"), ("eiweiß", "protein"), ("eiweiss", "protein"), ("salz", "salt")]
    for b in _group(d, "Nährwerte"):
        for row in b.get("table") or []:
            if len(row) < 2: continue
            k, v = row[0].lower(), row[1]
            if k.startswith("durchschnittliche"): basis = v; continue
            if k.startswith("brennwert"):
                m = re.search(r"(\d+(?:[.,]\d+)?)\s*kcal", v)
                if m: out["kcal"] = float(m.group(1).replace(",", "."))
                continue
            for needle, key in keymap:
                if needle in k: out[key] = _num(v); break
    macros = [out.get(k) for k in ("protein", "fat", "carbs")]
    if out.get("kcal") and all(m == 0 for m in macros if m is not None) and any(m is not None for m in macros):
        out = {"kcal": out["kcal"]}   # placeholder table (all macros 0 g) -> not trustworthy
    return out, basis

def product(dan: int, url: str | None = None) -> Product:
    d = get(API.format(dan=dan))
    brand = (d.get("brand") or {}).get("name")
    title = (d.get("title") or {}).get("headline") or ""
    nut, basis = parse_nutrition(d)
    m = re.search(r"(\d+(?:,\d+)?)\s*(g|kg|ml|l)\b", title, re.I) or re.search(r"Grundpreis:\s*(\d+(?:,\d+)?)\s*(g|kg|ml|l)\b", d.get("a11yLabel") or "", re.I)
    size = (float(m.group(1).replace(",", ".")) * (1000 if m.group(2).lower() in ("kg", "l") else 1)) if m else None
    imgs = [i["src"] for i in d.get("images") or [] if i.get("src") and not i.get("isAiGenerated")]
    price = _num((((d.get("price") or {}).get("price") or {}).get("current") or {}).get("value"))
    crumbs = d.get("breadcrumbs") or []
    clean = re.sub(r",\s*\d+(?:,\d+)?\s*(g|kg|ml|l)\s*$", "", title, flags=re.I).strip()
    return Product(source="dm", store="dm", name=f"{brand} {clean}".strip(), brand=brand, price_eur=price,
                   unit_price_eur=round(price / size * 1000, 2) if price and size else None, unit="kg" if size else None,
                   size_g=size, nutrition_100g=nut, ean=str(d["gtin"]) if d.get("gtin") else None, image_url=imgs[0] if imgs else None,
                   producer=(_texts(d, "Anschrift des Unternehmens") or "").split("\n")[0] or None,
                   origin=_texts(d, "Hergestellt in"), category=" > ".join(crumbs),
                   source_url=url or f"https://www.dm.at{d.get('self') or ''}", source_id=str(dan),
                   extra={"api": API.format(dan=dan), "nutrition_basis": basis, "breadcrumbs": crumbs,
                          "ingredients": _texts(d, "Zutaten"), "prep": _texts(d, "Verwendungshinweise"),
                          "price_note": ((d.get("price") or {}).get("notIncreasedSince") or {}).get("text")})

def is_ready_meal(p: Product) -> bool:
    c = p.extra.get("breadcrumbs") or []
    return c[:2] == ["Ernährung", "Fertiggerichte & Konserven"] and not (len(c) > 2 and c[2] == "Konserven") and not DROP_NAME.search(p.name)

class DmShop(Adapter):
    id = "dm"; store = "dm"; homepage = "https://www.dm.at"; status = "live"
    notes = ("Live: dm.at product sitemap + public products.dm.de product JSON (price, nutrition, GTIN, images, ingredients). "
             "No login/cookies; /search is robots-disallowed and not used, so search() matches query words against sitemap slugs.")
    delay = 1.0
    def _scan(self, urls, limit, keep=lambda p: True):
        out = []
        for u in urls:
            dan = int(re.search(r"/p/d/(\d+)/", u).group(1))
            try: p = product(dan, u)
            except Exception: continue
            finally: time.sleep(self.delay)
            if keep(p): out.append(p)
            if len(out) >= limit: break
        return out
    def search(self, q: str, limit: int = 20) -> list[Product]:
        words = [w for w in re.split(r"[^a-z0-9]+", q.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")) if w]
        urls = [u for u in sitemap_urls() if all(w in u.rsplit("/", 1)[1] for w in words)]
        return self._scan(urls[: limit * 3], limit)
    def fetch(self, category: str = "ready-meals", limit: int = 200) -> list[Product]:
        if category != "ready-meals": return self.search(category, limit)
        urls = [u for u in sitemap_urls() if SLUG.search(u.rsplit("/", 1)[1]) and not SLUG_NOT.search(u.rsplit("/", 1)[1])]
        return self._scan(urls, limit, is_ready_meal)
