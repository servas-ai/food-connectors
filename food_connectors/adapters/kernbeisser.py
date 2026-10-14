"""Kernbeißer (kernbeisser.at) — vegan whole-grain ready meals in glass jars from Vienna, AT-only delivery.

Sources (public, no login/cookies; robots.txt ``User-agent: *`` disallows only wp-admin, WooCommerce
upload/log folders and ``?add-to-cart=`` URLs — the Store API and product pages are allowed):
  * WooCommerce Store API ``https://kernbeisser.at/wp-json/wc/store/v1/products?per_page=100`` — the JSON the
    shop front-end itself uses: name, SKU, price (minor units, EUR incl. MwSt.), stock, images, tags
    (vegan / glutenfrei / ohne Zusatzstoffe …) and the long description, which carries the published
    'Durchschnittliche Nährwerte pro 100g' block, 'Zutaten:' and '… enthält 450g 522 kcal in einem Glas'.
  * product page ``https://kernbeisser.at/produkt/<slug>/`` — schema.org JSON-LD Product with ``gtin``
    (only fetched for the GTIN; optional).
Ready meals = simple products with a parsed nutrition block and jar size (the 'Probierpaket' bundle is
excluded). Shop rules (site header + FAQ): 9 € per glass, minimum order 6 glasses (6/12/18/24/30), free
shipping, delivery only within Austria.
Operator (kernbeisser.at/impressum): Kernbeißer OG, Jheringgasse 33/2/8, 1150 Wien, FN 622470y
(Handelsgericht Wien), UID ATU80744456 (EU VIES valid 2026-10-14, name 'Kernbeißer OG').
Polite 1 req/s.
"""
from __future__ import annotations
import html as _html, json, re, time
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://kernbeisser.at"
STORE = "Online: Kernbeißer"
PRODUCER = "Kernbeißer OG, Jheringgasse 33/2/8, 1150 Wien, FN 622470y"
SHIPPING_NOTE = "Kostenloser Versand, Lieferung nur innerhalb Österreichs; Mindestbestellmenge 6 Gläser (6/12/18/24/30) lt. kernbeisser.at"
_N = r"(\d+(?:[.,]\d+)?)"
NUT = (
    ("satfat", r"davon gesättigte Fettsäuren\s*" + _N + r"\s*g"),
    ("fat", r"(?<!gesättigte )Fett\s+" + _N + r"\s*g"),
    ("sugar", r"davon Zucker\*?\s*" + _N + r"\s*g"),
    ("carbs", r"Kohlenhydrate\s*" + _N + r"\s*g"),
    ("fiber", r"Ballaststoffe\s*" + _N + r"\s*g"),
    ("protein", r"Eiwei(?:ß|ss)\s*" + _N + r"\s*g"),
    ("salt", r"Salz\s*" + _N + r"\s*g"),
)


def _f(s):
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def parse_description(desc_html: str) -> dict:
    """Published text block → nutrition per 100 g, jar size, kcal per jar, ingredients."""
    t = _clean(desc_html)
    out = {"nutrition_100g": {}, "size_g": None, "kcal_jar": None, "ingredients": None, "preparation": None}
    m = re.search(r"enthält\s*" + _N + r"\s*g\s*" + _N + r"\s*kcal", t)
    if m:
        out["size_g"], out["kcal_jar"] = _f(m.group(1)), _f(m.group(2))
    blk = re.search(r"Nährwerte pro 100\s*g(.*?)(?:\*von Natur|Zubereitung|$)", t, re.S)
    if blk:
        b = blk.group(1)
        k = re.search(_N + r"\s*kJ\s*/\s*" + _N + r"\s*kcal", b)
        if k:
            out["nutrition_100g"]["kcal"] = _f(k.group(2))
        for key, rx in NUT:
            mm = re.search(rx, b)
            if mm:
                out["nutrition_100g"][key] = _f(mm.group(1))
    z = re.search(r"Zutaten:\s*(.*?)\s*Durchschnittliche Nährwerte", t, re.S)
    if z:
        out["ingredients"] = z.group(1).strip()
    p = re.search(r"Zubereitungsempfehlung:\s*(.*?\.)(?:\s|$)(.*?\.)?", t)
    if p:
        out["preparation"] = (p.group(1) + (" " + p.group(2) if p.group(2) else "")).strip()
    return out


def parse_gtin(page_html: str) -> str | None:
    m = re.search(r'"gtin\d*"\s*:\s*"(\d{8,14})"', page_html or "")
    if not m:
        return None
    g = m.group(1)
    if len(g) == 13:
        d = list(map(int, g))
        if (10 - sum(v * (1 if i % 2 == 0 else 3) for i, v in enumerate(d[:12])) % 10) % 10 != d[12]:
            return None
    return g


def is_meal(sp: dict) -> bool:
    if sp.get("type") != "simple":
        return False
    if re.search(r"probier|paket|gutschein|bundle", (sp.get("slug") or "") + " " + (sp.get("name") or ""), re.I):
        return False
    return True


def to_product(sp: dict, page_html: str | None = None) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    d = parse_description(sp.get("description") or "")
    size = d["size_g"]
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    tags = [t["name"] for t in (sp.get("tags") or [])]
    return Product(
        source="kernbeisser",
        store=STORE,
        name=_html.unescape(sp.get("name") or "").strip(),
        brand="Kernbeißer",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
        size_g=size,
        nutrition_100g=d["nutrition_100g"],
        ean=parse_gtin(page_html) if page_html else None,
        image_url=imgs[0] if imgs else None,
        producer=PRODUCER,
        category="Fertiggericht",
        source_url=sp.get("permalink") or f"{BASE}/produkt/{sp.get('slug')}/",
        source_id=sp.get("sku") or str(sp.get("id")),
        extra={
            "wc_id": sp.get("id"),
            "slug": sp.get("slug"),
            "in_stock": sp.get("is_in_stock"),
            "kcal_jar": d["kcal_jar"],
            "ingredients": d["ingredients"],
            "preparation": d["preparation"],
            "tags": tags,
            "vegan": any(t.lower() == "vegan" for t in tags),
            "glutenfrei": any(t.lower() == "glutenfrei" for t in tags),
            "images": imgs,
            "price_note": "Einzelpreis je Glas inkl. MwSt. lt. WooCommerce Store API (Mindestbestellung 6 Gläser)",
            "shipping_note": SHIPPING_NOTE,
            "portions": "1–2 (FAQ: 'Ein Glas enthält ein bis zwei Portionen')",
        },
    )


def is_ready_meal(p: Product) -> bool:
    n = p.nutrition_100g
    return bool(p.name and p.price_eur and p.size_g and n.get("kcal") is not None and n.get("protein") is not None)


def _page(sp: dict) -> str:
    try:
        return get(sp["permalink"], raw=True, timeout=40, headers={"Accept": "text/html"}).decode("utf-8", "replace")
    except Exception:
        return ""


def product(slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    slug = slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if p.get("slug") == slug or p.get("sku") == slug), None)
    if not sp:
        return None
    return to_product(sp, _page(sp))


class Kernbeisser(Adapter):
    id = "kernbeisser"
    store = STORE
    homepage = BASE
    notes = (
        "Live: public WooCommerce Store API (price, SKU, stock, images, description with Nährwerte pro 100 g, "
        "Zutaten, jar size) + product JSON-LD GTIN; vegan Vollkorn-Fertiggerichte im Glas (Wien); "
        "AT-only, free shipping, min. 6 glasses; polite 1 req/s"
    )
    delay = 1.0

    def fetch(self, category="ready-meals", limit=500):
        shop = store_products()
        out = []
        for sp in [p for p in shop if is_meal(p)][:limit]:
            time.sleep(self.delay)
            p = to_product(sp, _page(sp))
            if is_ready_meal(p):
                out.append(p)
        return out

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        shop = store_products()
        out = []
        for sp in [p for p in shop if is_meal(p)]:
            hay = (sp.get("name", "") + " " + sp.get("slug", "") + " " + _clean(sp.get("description", ""))).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp))
            if len(out) >= limit:
                break
        return out
