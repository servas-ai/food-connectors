"""Löwenanteil (loewenanteil.com) — organic high-protein ready meals in glass jars, shipped to DE + AT.

Sources (public, no login/cookies; robots User-agent:* Disallow includes /policies/ /cart /account /checkouts —
product pages + /products.json are allowed; shipping/legal-notice under /policies/ are NOT fetched):
  * Shopify storefront JSON ``https://www.loewenanteil.com/products.json`` (title, handle, product_type,
    tags, SKU, price EUR, availability, images on cdn.shopify.com / shop CDN).
  * product page ``https://www.loewenanteil.com/products/<handle>`` — server-rendered HTML with the
    Nährwerte table (pro 100 g + pro Glas (570 g)), Zutaten, Zubereitung, packshot.
Ready meals = product_type Fertiggericht, tag ``single``, not ``mm_pasta``, Shopify grams ≥ 800 (filled jar;
edible size comes from the published "pro Glas (N g)" column, typically 570 g). No GTIN published → ean None.
AT delivery: storefront country selector lists "Österreich (EUR €)" on the homepage (allowed page). Exact
shipping fee lives only under /policies/shipping-policy (robots Disallow) → shipping_eur left null; not invented.
Operator: Löwenanteil GmbH, Heiligengeiststraße 6–8, 26121 Oldenburg (DE), HRB 212808 AG Oldenburg,
USt-ID DE316057151 (North Data / online-handelsregister.de public extract; footer © Löwenanteil GmbH;
/policies/legal-notice not fetched due to robots).
Polite 1 req/s.
"""
from __future__ import annotations
import html as _html, json, re, time
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.loewenanteil.com"
STORE = "Online: Löwenanteil"
PRODUCER = "Löwenanteil GmbH, Heiligengeiststraße 6–8, 26121 Oldenburg (DE), HRB 212808"
SHIPPING_NOTE = (
    "AT selectable on storefront (homepage country switcher 'Österreich (EUR €)'); "
    "/policies/shipping-policy is robots-Disallow — fee not scraped, shipping_eur left null"
)
_NUM = r"(\d+(?:[.,]\d+)?)"
NUT_KEYS = (
    ("kcal", r"brennwert|energie"),
    ("satfat", r"gesättigt"),
    ("fat", r"^fett\b"),
    ("sugar", r"zucker"),
    ("carbs", r"kohlenhydrat"),
    ("fiber", r"ballast"),
    ("protein", r"eiwei|protein"),
    ("salt", r"salz"),
)


def _f(s):
    if s is None:
        return None
    s = str(s).strip().replace("\xa0", " ").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def shop_products(pages: int = 2) -> list[dict]:
    out = []
    for page in range(1, pages + 1):
        d = get(f"{BASE}/products.json?limit=250&page={page}", timeout=40)
        ps = d.get("products") or []
        out += ps
        if len(ps) < 250:
            break
        time.sleep(1.0)
    return out


def _tags(sp: dict) -> list[str]:
    t = sp.get("tags") or []
    if isinstance(t, str):
        return [x.strip() for x in t.split(",") if x.strip()]
    return list(t)


def is_meal(sp: dict) -> bool:
    """Single ready-meal glass jars (exclude pasta sides, broth, bundles, merch)."""
    v = (sp.get("variants") or [{}])[0]
    price = float(v.get("price") or 0)
    grams = float(v.get("grams") or 0)
    tags = {t.lower() for t in _tags(sp)}
    ptype = (sp.get("product_type") or "").lower()
    handle = (sp.get("handle") or "").lower()
    if not ptype.startswith("fertiggericht"):
        return False
    if "single" not in tags or "mm_pasta" in tags:
        return False
    if grams < 800 or price < 7:
        return False
    if re.search(r"knochen|bruhe|brühe|hoodie|gutschein|beileger|pasta|bundle|probier", handle):
        return False
    return True


def parse_nutrition(html: str) -> tuple[dict, dict, float | None]:
    """Parse the published Nährwerte table → (per100, per_glas, size_g)."""
    # Find the nutrition table block
    m = re.search(
        r"<table>\s*<tbody>\s*<tr>\s*<td>\s*<strong>\s*Nährwerte\s*</strong>\s*</td>"
        r".*?</table>",
        html,
        re.S | re.I,
    )
    if not m:
        # looser: any table that has Brennwert + pro 100
        m = re.search(r"<table>\s*<tbody>.*?Brennwert.*?</table>", html, re.S | re.I)
    if not m:
        return {}, {}, None
    table = m.group(0)
    size = None
    sm = re.search(r"pro Glas\s*\((\d+)\s*g\)", table, re.I)
    if sm:
        size = float(sm.group(1))
    per100, perpack = {}, {}
    # Split rows; label cell may contain "Fett<br>davon gesättigt"
    rows = re.findall(r"<tr>(.*?)</tr>", table, re.S | re.I)
    for row in rows[1:]:  # skip header
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
        if len(cells) < 3:
            continue
        lab_html, c100, cpack = cells[0], cells[1], cells[2]
        # Split compound labels (Fett / davon gesättigt) into sub-rows by <br>
        labs = re.split(r"<br\s*/?>", lab_html, flags=re.I)
        v100s = re.split(r"<br\s*/?>", c100, flags=re.I)
        vpacks = re.split(r"<br\s*/?>", cpack, flags=re.I)
        for i, lab_raw in enumerate(labs):
            lab = _clean(lab_raw).lower().lstrip("–-— ").strip()
            if not lab or lab.startswith("nährwert"):
                continue
            key = next((k for k, rx in NUT_KEYS if re.search(rx, lab)), None)
            if not key:
                continue
            cell100 = v100s[i] if i < len(v100s) else ""
            cellpack = vpacks[i] if i < len(vpacks) else ""
            if key == "kcal":
                # "348 kJ/83 kcal" or "357 kJ / 85 kcal"
                mm = re.search(_NUM + r"\s*kJ\s*/\s*" + _NUM + r"\s*kcal", _clean(cell100), re.I)
                vv = _f(mm.group(2)) if mm else None
                mm2 = re.search(_NUM + r"\s*kJ\s*/\s*" + _NUM + r"\s*kcal", _clean(cellpack), re.I)
                pv = _f(mm2.group(2)) if mm2 else None
            else:
                mm = re.search(_NUM, _clean(cell100).replace(",", "."))
                vv = _f(mm.group(1)) if mm else None
                mm2 = re.search(_NUM, _clean(cellpack).replace(",", "."))
                pv = _f(mm2.group(1)) if mm2 else None
            if vv is not None:
                per100[key] = vv
            if pv is not None:
                perpack[key] = pv
    return per100, perpack, size


def parse_ingredients(html: str) -> str | None:
    m = re.search(
        r'data-action="toggle-collapsible"[^>]*>\s*Zutaten\s*<.*?<div class="Rte">(.*?)</div>\s*</div>\s*</div>',
        html,
        re.S | re.I,
    )
    if not m:
        m = re.search(r">\s*Zutaten\s*<.*?<div class=\"Rte\">(.*?)</div>", html, re.S | re.I)
    if not m:
        return None
    t = _clean(m.group(1))
    return t or None


def parse_preparation(html: str) -> str | None:
    m = re.search(
        r'data-action="toggle-collapsible"[^>]*>\s*Zubereitung\s*<.*?<div class="Rte">(.*?)</div>\s*</div>\s*</div>',
        html,
        re.S | re.I,
    )
    if not m:
        return None
    t = _clean(m.group(1))
    # drop leading step chrome
    return t or None


def to_product(sp: dict, html: str | None, url: str | None = None) -> Product:
    v = (sp.get("variants") or [{}])[0]
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    # Prefer absolute https
    imgs = [("https:" + u if u.startswith("//") else u) for u in imgs]
    per100, perpack, size = parse_nutrition(html or "")
    price = float(v["price"]) if v.get("price") else None
    tags = _tags(sp)
    handle = sp.get("handle") or ""
    vegan = any(t.lower() == "vegan" for t in tags)
    bio = True  # brand is Bio; product pages show Bio seals; tag set does not always include "bio"
    return Product(
        source="loewenanteil",
        store=STORE,
        name=(sp.get("title") or "").strip(),
        brand="Löwenanteil",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
        size_g=size,
        nutrition_100g=per100,
        ean=None,
        image_url=imgs[0] if imgs else None,
        producer=PRODUCER,
        category="Fertiggericht",
        source_url=url or f"{BASE}/products/{handle}",
        source_id=v.get("sku") or handle,
        extra={
            "handle": handle,
            "shopify_id": sp.get("id"),
            "available": v.get("available"),
            "shopify_grams": v.get("grams"),
            "pack_nutrition": perpack,
            "ingredients": parse_ingredients(html or ""),
            "preparation": parse_preparation(html or ""),
            "vegan": vegan,
            "bio": bio,
            "tags": tags,
            "images": imgs,
            "price_note": "Einzelpreis EUR lt. Shopify products.json (Abo/Bundle günstiger)",
            "shipping_note": SHIPPING_NOTE,
            "portions": 2,  # product pages: "Portionen pro Glas: 2"
        },
    )


def product(handle_or_url: str, shop: list[dict] | None = None) -> Product | None:
    handle = handle_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    sp = next((p for p in (shop if shop is not None else shop_products()) if p.get("handle") == handle), None)
    if not sp:
        return None
    url = f"{BASE}/products/{handle}"
    try:
        # http.get defaults Accept to application/json first → Shopify returns .json body;
        # force text/html so we get the Nährwerte table in the product page HTML.
        h = get(url, raw=True, timeout=40, headers={"Accept": "text/html,application/xhtml+xml;q=0.9"}).decode("utf-8", "replace")
    except Exception:
        h = ""
    return to_product(sp, h, url)


def is_ready_meal(p: Product) -> bool:
    return bool(p.name) and bool(p.price_eur) and bool(p.size_g) and p.nutrition_100g.get("protein") is not None and p.nutrition_100g.get("kcal") is not None


class Loewenanteil(Adapter):
    id = "loewenanteil"
    store = STORE
    homepage = BASE
    notes = (
        "Live: public Shopify products.json (price, SKU, availability, images) + product HTML "
        "(Nährwerte pro 100 g / pro Glas, Zutaten, Zubereitung); Bio glass-jar ready meals; "
        "AT via storefront country selector (shipping fee under robots-Disallow /policies/); "
        "no GTIN; polite 1 req/s"
    )
    delay = 1.0

    def fetch(self, category="ready-meals", limit=500):
        shop = shop_products()
        out = []
        for sp in [p for p in shop if is_meal(p)][:limit]:
            time.sleep(self.delay)
            p = product(sp["handle"], shop)
            if p and is_ready_meal(p):
                out.append(p)
        return out

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        shop = shop_products()
        hits = [
            p
            for p in shop
            if is_meal(p)
            and all(w in (p["title"] + " " + p["handle"] + " " + " ".join(_tags(p))).lower() for w in words)
        ]
        out = []
        for sp in hits[:limit]:
            time.sleep(self.delay)
            p = product(sp["handle"], shop)
            if p:
                out.append(p)
        return out
