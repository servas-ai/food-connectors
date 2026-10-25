"""every. (every-foods.com) — frozen plant-based ready meals (bowls, curries, pasta, stews), shipped frozen with dry ice
to Germany **and Austria** (DPD) per the shop's own shipping policy (eat.every-foods.com/policies/shipping-policy:
"Österreich (DPD) … Wir liefern Dein Paket … in Deutschland, Österreich, Dänemark, Niederlande, Belgien und Luxemburg";
regular shipping 5,99 €, free from 8 meals). Note: the older AGB §6 still says "nur … in Deutschland" — recorded as a
conflict in ``extra.shipping_note``.

Sources (both public, no login/cookies, robots `*` allows /products/; only /account /api /discount disallowed):
  * Shopify storefront JSON ``https://eat.every-foods.com/products.json`` (title, handle, product_type, tags, SKU,
    price in EUR, availability, images on cdn.shopify.com). This is the DE/AT ("da") store; CH/BNL are separate shops.
  * product page ``https://every-foods.com/products/<handle>`` (Next.js + Storyblok): the embedded ``product`` blok has
    product_weight (g), the nutrition table per 100 g + per pack, ingredients (incl. "für AT: Fisolen" labels),
    preparation, short description, filters.
  * product sitemap ``https://every-foods.com/sitemap-products.xml`` = what the storefront currently lists.
Ready meals = product_type "Meal", price > 0 (gift/free SKUs excluded), handle listed in the DE sitemap. GTIN: empty in
products.json but published per variant on ``eat.every-foods.com/products/<handle>.json`` → read via ``shopify_gtin``
(GS1 check digit, shared codes dropped; verified 2026-10-25). Polite 1 req/s.
Operator: Every. GmbH, Ritterstraße 9–10, 10969 Berlin, HRB 221768 B (AG Charlottenburg), USt-ID DE335586517 (public Impressum).
"""
from __future__ import annotations
import json, re, time
from .base import Adapter
from ..http import get
from ..schema import Product
from .shopify_gtin import gtin, enrich, drop_shared

SHOP = "https://eat.every-foods.com"
BASE = "https://every-foods.com"
SITEMAP = BASE + "/sitemap-products.xml"
STORE = "Online: every."
SHIPPING_NOTE = ("Versand nach AT per DPD lt. eat.every-foods.com/policies/shipping-policy (DE, AT, DK, NL, BE, LU); "
                 "5,99 €, ab 8 Gerichten frei; Express 7,99 €. AGB §6 nennt noch 'nur Deutschland' (Konflikt dokumentiert)")
_NUM = r"(\d+(?:[.,]\d+)?)"
# German and English table labels (some Storyblok bloks are still in English: "Typical values", "of which sugar")
NUT_ROWS = (("kcal", r"energ|brennwert"), ("satfat", r"gesättigt|saturat"), ("fat", r"^(fett|fat)\b"), ("sugar", r"zucker|sugar"),
            ("carbs", r"kohlenhydrat|carbohydrat"), ("fiber", r"ballast|fib(er|re)"), ("protein", r"eiwei|protein"), ("salt", r"salz|salt"))


def _f(s):
    if s is None: return None
    s = s.strip().lstrip("<").strip().replace(",", ".")
    try: return float(s)
    except ValueError: return None


def shop_products(pages: int = 4) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        d = get(f"{SHOP}/products.json?limit=250&page={page}", timeout=40)
        ps = d.get("products") or []
        out += ps
        if len(ps) < 250: break
        time.sleep(1.0)
    return out


def sitemap_handles(xml: str | None = None) -> set[str]:
    xml = xml if xml is not None else get(SITEMAP, raw=True, timeout=40).decode("utf-8", "replace")
    return set(re.findall(r"<loc>https://every-foods\.com/products/([^<]+)</loc>", xml))


def is_meal(sp: dict, handles: set[str] | None = None) -> bool:
    v = (sp.get("variants") or [{}])[0]
    if sp.get("product_type") != "Meal" or not float(v.get("price") or 0) > 0: return False
    if re.search(r"test|gutschein|gift", sp.get("handle", "") + " " + sp.get("title", ""), re.I): return False
    return handles is None or sp.get("handle") in handles


def _rsc(h: str) -> str:
    return "".join(json.loads(m.group(1)) for m in re.finditer(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', h))


def product_blok(h: str) -> dict | None:
    s = _rsc(h); dec = json.JSONDecoder()
    for m in re.finditer(r'"blok":\{', s):
        try: o, _ = dec.raw_decode(s, m.end() - 1)
        except ValueError: continue
        if isinstance(o, dict) and o.get("component") == "product" and "nutritional_values" in o: return o
    return None


def doc_text(doc) -> str | None:
    if not doc: return None
    if isinstance(doc, str): return doc.strip() or None
    r: list[str] = []
    def w(n):
        if n.get("type") == "text": r.append(n.get("text", ""))
        elif n.get("type") == "hard_break": r.append("\n")
        for c in n.get("content") or []: w(c)
        if n.get("type") == "paragraph": r.append("\n")
    w(doc)
    t = re.sub(r"\n{3,}", "\n\n", "".join(r)).strip()
    return t or None


def nutrition_table(doc) -> tuple[dict, dict, str | None]:
    """Storyblok table → (per 100 g, per pack, header of the 100 g column)."""
    rows = []
    def find(n):
        if n.get("type") == "tableRow":
            rows.append([doc_text({"content": c.get("content") or []}) or "" for c in n.get("content") or []])
        else:
            for c in n.get("content") or []: find(c)
    if doc: find(doc)
    if not rows: return {}, {}, None
    hdr = rows[0]
    i100 = next((i for i, c in enumerate(hdr) if "100" in c), 1)
    ipack = next((i for i, c in enumerate(hdr) if i != i100 and re.search(r"packung|portion|\d+\s*g", c, re.I)), None)
    per100, perpack = {}, {}
    for r in rows[1:]:
        lab = (r[0] or "").lower().strip()
        key = next((k for k, rx in NUT_ROWS if re.search(rx, lab)), None)
        if not key: continue
        for idx, tgt in ((i100, per100), (ipack, perpack)):
            if idx is None or idx >= len(r): continue
            cell = r[idx]
            if key == "kcal":
                m = re.search(_NUM + r"\s*/\s*" + _NUM, cell) or re.search(_NUM + r"\s*kcal", cell)
                v = _f(m.group(m.lastindex)) if m else None
            else:
                m = re.search(r"<?\s*" + _NUM, cell); v = _f(m.group(1)) if m else None
            if v is not None: tgt[key] = v
    return per100, perpack, hdr[i100] if i100 < len(hdr) else None


def pack_check(per100: dict, perpack: dict, weight: float | None) -> list[str]:
    """Nutrients whose published per-pack value deviates >15 % from per-100 g × weight (source typos; per 100 g is used)."""
    if not weight: return []
    bad = []
    for k, v in per100.items():
        pv = perpack.get(k)
        if pv is None or v is None: continue
        exp = v * weight / 100
        if exp >= 1 and abs(pv - exp) / exp > 0.15: bad.append(k)
    return bad


def to_product(sp: dict, blok: dict | None, url: str | None = None) -> Product:
    v = (sp.get("variants") or [{}])[0]
    imgs = [i["src"] for i in sp.get("images") or [] if i.get("src")]
    b = blok or {}
    per100, perpack, per = nutrition_table(b.get("nutritional_values"))
    w = _f(str(b.get("product_weight") or "")) if b.get("product_weight") else None
    price = float(v["price"]) if v.get("price") else None
    tags = sp.get("tags") or []
    return Product(source="every", store=STORE, name=(b.get("name") or sp.get("title") or "").strip(), brand="every.",
                   price_eur=price, unit_price_eur=round(price / w * 1000, 2) if price and w else None, unit="kg" if price and w else None,
                   size_g=w, nutrition_100g=per100, ean=gtin(v), image_url=imgs[0] if imgs else None,
                   producer="Every. GmbH, Ritterstraße 9–10, 10969 Berlin (DE), HRB 221768 B", category=next((t.split("__", 1)[1] for t in tags if t.startswith("subtype__")), None),
                   source_url=url or f"{BASE}/products/{sp.get('handle')}", source_id=v.get("sku") or sp.get("handle"),
                   extra={"handle": sp.get("handle"), "shopify_id": sp.get("id"), "available": v.get("available"),
                          "compare_at_price": float(v["compare_at_price"]) if v.get("compare_at_price") else None,
                          "pack_nutrition": perpack, "nutrition_per": per, "pack_inconsistent": pack_check(per100, perpack, w), "short_description": doc_text(b.get("short_description")),
                          "description": doc_text(b.get("description")), "ingredients": doc_text(b.get("ingredients")),
                          "preparation": doc_text(b.get("preparation")), "spiciness": b.get("spiciness_filter") or None,
                          "nutrition_filter": b.get("nutrition_filter") or [], "base": b.get("base_filter") or None,
                          "vegan": "Vegan" in tags, "tags": tags, "images": imgs,
                          "price_note": "Einzelpreis EUR lt. Shopify products.json (DE/AT-Shop); Bundles/Abo günstiger",
                          "shipping_note": SHIPPING_NOTE})


def product(handle_or_url: str, shop: list[dict] | None = None) -> Product | None:
    handle = handle_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    sp = next((p for p in (shop if shop is not None else shop_products()) if p.get("handle") == handle), None)
    if not sp: return None
    enrich(SHOP, sp)
    url = f"{BASE}/products/{handle}"
    try: h = get(url, raw=True, timeout=40).decode("utf-8", "replace")
    except Exception: h = ""
    return to_product(sp, product_blok(h) if h else None, url)


def is_ready_meal(p: Product) -> bool:
    return bool(p.name) and bool(p.price_eur) and bool(p.size_g) and p.nutrition_100g.get("protein") is not None


class Every(Adapter):
    id = "every"; store = STORE; homepage = BASE
    notes = ("Live: public Shopify storefront JSON (eat.every-foods.com/products.json: price, SKU, availability, images) + "
             "product pages (Storyblok blok: weight, nutrition per 100 g/pack, ingredients, preparation); frozen plant-based "
             "ready meals shipped to AT (DPD, 5,99 €, free from 8 meals); GTIN via per-product JSON; polite 1 req/s")
    delay = 1.0
    def fetch(self, category="ready-meals", limit=500):
        shop = shop_products(); time.sleep(self.delay)
        handles = sitemap_handles(); out = []
        for sp in [p for p in shop if is_meal(p, handles)][:limit]:
            time.sleep(self.delay)
            p = product(sp["handle"], shop)
            if p and is_ready_meal(p): out.append(p)
        return drop_shared(out)
    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        shop = shop_products(); handles = sitemap_handles()
        hits = [p for p in shop if is_meal(p, handles) and all(w in (p["title"] + " " + p["handle"] + " " + " ".join(p.get("tags") or [])).lower() for w in words)]
        out = []
        for sp in hits[:limit]:
            time.sleep(self.delay)
            p = product(sp["handle"], shop)
            if p: out.append(p)
        return out
