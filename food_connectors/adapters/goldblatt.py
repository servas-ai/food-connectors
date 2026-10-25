"""Goldblatt (goldblatt.at) — High Protein Bio glass-jar ready meals from Steiermark, ships AT (+ DE).

Sources (public, no login/cookies; robots.txt ``User-agent: * Allow: /`` — product pages, /products.json
and /policies/shipping-policy + /policies/legal-notice are crawlable):
  * Shopify storefront JSON ``https://goldblatt.at/products.json`` — title, handle, product_type,
    tags, SKU, price EUR, availability, images (cdn.shopify.com / goldblatt.at/cdn).
  * product page ``https://goldblatt.at/products/<handle>`` — server-rendered HTML with Zutaten text,
    Nährwerte table (pro 100 g + pro Glas (500 g)), Zubereitung steps.
Ready meals = product_type ``High Protein Bio-Fertiggerichte``, single SKU (not bundle/probier/monats),
Shopify grams ≈ 883 (glass jar shipping weight); edible size from the published "pro Glas (N g)" column
(typically 500 g). GTIN: empty in products.json but published per variant on ``/products/<handle>.json``
→ read via ``shopify_gtin`` (8/8 meals, 2026-10-25).
AT delivery: ``/policies/shipping-policy`` — "Wir liefern innerhalb Österreichs sowie ins EU-Ausland und
die Schweiz"; Inland ab 30 € = 5,99 € (darunter 9,99 €), gratis ab 90 €; Österreichische Post 1–3 Werktage.
Operator (goldblatt.at/policies/legal-notice): Golden Veggies GmbH, Wagerberg 37, 8271 Bad Waltersdorf,
FN 550344f (Landesgericht Graz), UID ATU76525048 (EU VIES valid, name+address match).
Polite 1 req/s.
"""
from __future__ import annotations
import html as _html, re, time
from .base import Adapter
from ..http import get
from ..schema import Product
from .shopify_gtin import gtin, enrich, drop_shared

BASE = "https://goldblatt.at"
STORE = "Online: Goldblatt"
PRODUCER = "Golden Veggies GmbH, Wagerberg 37, 8271 Bad Waltersdorf, FN 550344f"
SHIPPING_NOTE = (
    "AT lt. goldblatt.at/policies/shipping-policy: Inland ab 30 € pauschal 5,99 € (darunter 9,99 €), "
    "gratis ab 90 €; Post 1–3 Werktage; auch DE (7,99 € ab 30 € / gratis ab 99 €)"
)
_NUM = r"(\d+(?:[.,]\d+)?)"
NUT_KEYS = (
    ("kcal", r"energie|brennwert"),
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
    """Single High Protein Bio-Fertiggerichte jars (exclude bundles, merch, wurst, toppings)."""
    v = (sp.get("variants") or [{}])[0]
    price = float(v.get("price") or 0)
    grams = float(v.get("grams") or 0)
    tags = {t.lower() for t in _tags(sp)}
    ptype = (sp.get("product_type") or "").lower()
    handle = (sp.get("handle") or "").lower()
    title = (sp.get("title") or "").lower()
    if "fertiggericht" not in ptype:
        return False
    if "bundle" in tags or "bundle" in ptype:
        return False
    if re.search(r"probier|paket|monats|bundle|geschenk|gutschein|vorrat", handle + " " + title):
        return False
    # Single jars: ~883 g shipping weight, ~12 €; reject empty shipping weight
    if grams < 500 or price < 8:
        return False
    return True


def parse_nutrition(html: str) -> tuple[dict, dict, float | None]:
    """Parse the published Nährwerte table → (per100, per_glas, size_g)."""
    m = re.search(
        r"<table>\s*<thead>\s*<tr>\s*<th></th>\s*<th>\s*pro 100\s*g\s*</th>"
        r".*?</table>",
        html,
        re.S | re.I,
    )
    if not m:
        m = re.search(
            r"<table>\s*<thead>.*?pro 100\s*g.*?pro Glas.*?</table>",
            html,
            re.S | re.I,
        )
    if not m:
        m = re.search(r"<table>\s*<thead>.*?Energie.*?Eiwei.*?</table>", html, re.S | re.I)
    if not m:
        return {}, {}, None
    table = m.group(0)
    size = None
    sm = re.search(r"pro Glas\s*\((\d+)\s*g\)", table, re.I)
    if sm:
        size = float(sm.group(1))
    per100, perpack = {}, {}
    rows = re.findall(r"<tr>(.*?)</tr>", table, re.S | re.I)
    for row in rows:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S | re.I)
        if len(cells) < 3:
            continue
        lab = _clean(cells[0]).lower().lstrip("–-— ").strip()
        if not lab or lab.startswith("pro ") or lab.startswith("nährwert"):
            continue
        key = next((k for k, rx in NUT_KEYS if re.search(rx, lab)), None)
        if not key:
            continue
        cell100, cellpack = cells[1], cells[2]
        if key == "kcal":
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
    # Prefer the plaintext "Zutaten: …" block that sits next to the nutrition accordion
    plain = _clean(html)
    m = re.search(
        r"Zutaten:\s*(.*?)\s*(?:°aus kontrolliert|AT-BIO|ø\s*Nährwert|Nährwertangaben)",
        plain,
        re.S | re.I,
    )
    if m:
        t = m.group(1).strip()
        # keep bio footnote short
        return (t + " °aus kontrolliert biologischer Landwirtschaft.").strip() if t else None
    m = re.search(r"Zutaten:\s*(.{20,900}?)(?:ø Nährwert|Nährwertangaben|Zubereitung)", plain, re.S | re.I)
    if m:
        return m.group(1).strip() or None
    return None


def parse_preparation(html: str) -> str | None:
    plain = _clean(html)
    m = re.search(
        r"Zubereitung(?:\s*&(?:amp;)?\s*Tipps)?\s*"
        r"((?:\d+\.\s*.*?(?:Topf|Mikrowelle|Genießen).*?){1,4})",
        plain,
        re.S | re.I,
    )
    if m:
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        # stop before emoji tip / Qualität
        t = re.split(r"(?:👉|Qualitätsversprechen|Versand\s*&)", t)[0].strip()
        return t or None
    return None


def to_product(sp: dict, html: str | None, url: str | None = None) -> Product:
    v = (sp.get("variants") or [{}])[0]
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    imgs = [("https:" + u if u.startswith("//") else u) for u in imgs]
    per100, perpack, size = parse_nutrition(html or "")
    price = float(v["price"]) if v.get("price") else None
    tags = _tags(sp)
    handle = sp.get("handle") or ""
    vegan = any(t.lower() in ("pflanzlich", "vegan") for t in tags) or True  # brand is 100% plant-based
    bio = True  # product_type + AT-BIO-301 on every meal page
    return Product(
        source="goldblatt",
        store=STORE,
        name=(sp.get("title") or "").strip(),
        brand="Goldblatt",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
        size_g=size,
        nutrition_100g=per100,
        ean=gtin(v),
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
            "price_note": "Einzelpreis EUR lt. Shopify products.json (Pakete/Bundles günstiger)",
            "shipping_note": SHIPPING_NOTE,
            "portions": 2,  # FAQ: 500 g Glas = 2 Portionen mit Beilage
            "bio_code": "AT-BIO-301",
        },
    )


def product(handle_or_url: str, shop: list[dict] | None = None) -> Product | None:
    handle = handle_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    sp = next((p for p in (shop if shop is not None else shop_products()) if p.get("handle") == handle), None)
    if not sp:
        return None
    if shop is None:
        enrich(BASE, sp)
    url = f"{BASE}/products/{handle}"
    try:
        h = get(url, raw=True, timeout=40, headers={"Accept": "text/html,application/xhtml+xml;q=0.9"}).decode(
            "utf-8", "replace"
        )
    except Exception:
        h = ""
    return to_product(sp, h, url)


def is_ready_meal(p: Product) -> bool:
    return (
        bool(p.name)
        and bool(p.price_eur)
        and bool(p.size_g)
        and p.nutrition_100g.get("protein") is not None
        and p.nutrition_100g.get("kcal") is not None
    )


class Goldblatt(Adapter):
    id = "goldblatt"
    store = STORE
    homepage = BASE
    notes = (
        "Live: public Shopify products.json (price, SKU, availability, images) + product HTML "
        "(Nährwerte pro 100 g / pro Glas 500 g, Zutaten, Zubereitung); Bio glass-jar ready meals "
        "from Steiermark; AT shipping published on /policies/shipping-policy (5,99 € ab 30 € / "
        "gratis ab 90 €); GTIN from per-product JSON; polite 1 req/s"
    )
    delay = 1.0

    def fetch(self, category="ready-meals", limit=500):
        shop = shop_products()
        out = []
        for sp in [p for p in shop if is_meal(p)][:limit]:
            time.sleep(self.delay)
            enrich(BASE, sp)
            p = product(sp["handle"], shop)
            if p and is_ready_meal(p):
                out.append(p)
        return drop_shared(out)

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
