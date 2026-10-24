"""SUPPITO (suppito.at) — Viennese jar-soup and stew kitchen (Dr. Andrea Scholdan GmbH) selling its own chilled,
preservative-free soups and Eintöpfe in glass jars online, shipped Austria-wide.

Source (public, no login/cookies; robots.txt ``User-agent: *`` disallows only wp-admin and ``?add-to-cart=``):
  * WooCommerce Store API ``https://www.suppito.at/wp-json/wc/store/v1/products?per_page=100`` — the JSON the
    shop front-end uses: name, price (minor units, EUR incl. 10 % MwSt.), stock, categories, tags
    (vegan/vegetarisch/glutenfrei), images, ingredient list (short description) and the WooCommerce Germanized
    extension with net content (``unit_product`` g) and unit price per 100 g.
Ready meals = categories 'Suppen' and 'Eintöpfe' minus sauces (Gemüsesugo, Ragu alla Bolognese), clear broths
(Brodo) and salad dressing; sweet porridges ('Süsse Eintöpfe'), spices, drinks and cookbooks are skipped.
No nutrition table and no GTIN are published → never estimated.
Shipping (suppito.at/lieferbedingungen/, read 2026-10-24): Austria-wide chilled Post parcel 10 € per box,
minimum order 70 €, order Wed–Tue, dispatched Wednesday, delivered Thu/Fri; Vienna courier 10 € (Mon–Thu).
Storage (FAQ): chilled, 3–15 weeks shelf life, glass jars without deposit.
Operator (suppito.at/impressum/): Dr. Andrea Scholdan GmbH, Girardigasse 9, 1060 Wien, FN 571100d (HG Wien),
UID ATU77606002 (EU VIES valid 2026-10-24, same name and address).
Photos: Store API images only; the Butterbeans product reuses the Gigantes jar photo → dropped (vision gate).
Polite: one request per call.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.suppito.at"
STORE = "Online: SUPPITO"
PRODUCER = "Dr. Andrea Scholdan GmbH (SUPPITO), Girardigasse 9, 1060 Wien (FN 571100d, UID ATU77606002)"
SHIPPING_EUR = 10.0
SHIPPING_NOTE = ("Post-Kühlversand österreichweit 10 € je Box, Mindestbestellwert 70 €, Versand Mittwoch, Zustellung Do/Fr; "
                 "Wien-Botendienst 10 € (Mo–Do) lt. suppito.at/lieferbedingungen/")
STORAGE = "gekühlt (Glas, eingekocht)"
SHELF_LIFE = "3–15 Wochen gekühlt lt. FAQ"
MEAL_CATS = {"Suppen", "Eintöpfe"}
EXCLUDE = re.compile(r"dressing|sugo|bolognese|brodo|fond\b|gutschein", re.I)
# vision gate 2026-10-24: product shows another product's photo
BAD_PHOTO = {51447: "Gigantes-Kopie-jpg.webp"}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def is_meal(sp: dict) -> bool:
    cats = {_html.unescape(c.get("name", "")) for c in (sp.get("categories") or [])}
    if not cats & MEAL_CATS:
        return False
    return not EXCLUDE.search(_html.unescape(sp.get("name") or "") + " " + (sp.get("slug") or ""))


def to_product(sp: dict) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    gz = (sp.get("extensions") or {}).get("woocommerce-germanized") or {}
    size = float(gz["unit_product"]) if gz.get("unit") == "g" and gz.get("unit_product") else None
    up = gz.get("unit_prices") or {}
    unit_price = int(up["price"]) / 10 ** mu if up.get("price") and gz.get("unit_base") == "100" else None
    tags = [_html.unescape(t.get("name", "")).lower() for t in (sp.get("tags") or [])]
    cats = [_html.unescape(c.get("name", "")) for c in (sp.get("categories") or [])]
    ingr = _clean(sp.get("short_description") or "")
    bad = BAD_PHOTO.get(sp.get("id"))
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src") and not (bad and i["src"].endswith(bad))]
    name = _html.unescape(sp.get("name") or "").strip()
    return Product(
        source="suppito",
        store=STORE,
        name=name,
        brand="SUPPITO",
        price_eur=price,
        unit_price_eur=unit_price,
        unit="100 g" if unit_price else None,
        size_g=size,
        nutrition_100g={},
        ean=None,
        image_url=imgs[0] if imgs else None,
        producer=PRODUCER,
        category="Fertiggericht",
        source_url=sp.get("permalink") or f"{BASE}/produkt/{sp.get('slug')}/",
        source_id=str(sp.get("id")),
        extra={
            "wc_id": sp.get("id"),
            "slug": sp.get("slug"),
            "in_stock": sp.get("is_in_stock"),
            "line": "Suppe" if "Suppen" in cats else "Eintopf",
            "vegan": "vegan" in tags,
            "vegetarian": "vegan" in tags or "vegetarisch" in tags,
            "gluten_free": "glutenfrei" in tags,
            "bio_claim": bool(re.search(r"\bBio\b", name + " " + ingr)),
            "ingredients": ingr or None,
            "images": imgs,
            "storage": STORAGE,
            "shelf_life": SHELF_LIFE,
            "price_note": "Preis je Glas inkl. 10 % MwSt. lt. WooCommerce Store API (Germanized Grundpreis je 100 g)",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(id_slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or p.get("slug") == k), None)
    return to_product(sp) if sp else None


class Suppito(Adapter):
    id = "suppito"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of SUPPITO (Dr. Andrea Scholdan GmbH, Wien): chilled jar soups and "
             "Eintöpfe 500–520 g, price incl. MwSt., €/100 g, stock, ingredients, vegan/vegetarisch/glutenfrei tags, "
             "photos where published; Post-Kühlversand AT 10 €/box, min. 70 €; no nutrition/GTIN; 1 request per call")

    def fetch(self, category="ready-meals", limit=500):
        return [to_product(sp) for sp in store_products() if is_meal(sp)][:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if not is_meal(sp):
                continue
            hay = (sp.get("name", "") + " " + sp.get("slug", "") + " " + _clean(sp.get("short_description", ""))).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp))
        return out[:limit]
