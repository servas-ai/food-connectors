"""Deflorian Tiefkühlspezialitäten (deflorian.tirol) — Deflorian Tiefkühlspezialitäten GmbH, Hnr. 35b, 6069 Gnadenwald
(Tirol; UID ATU64259769, VIES valid 2026-10-25 'Deflorian Tiefkühlspezialitäten GmbH', Landesgericht Innsbruck): the
producer's own Shopify webshop for hand-made frozen Tyrolean dishes (Schlutzkrapfen, Knödel, Kaskrapfen, Gulasch, soups).

Source (public Shopify storefront, no login/cookies; robots.txt ``User-agent: *`` ``Allow: /``):
  * ``https://deflorian.tirol/products.json?limit=250`` — title, tags (shop category), variants (first = smallest pack:
    price EUR incl. MwSt., Shopify weight in g, availability), description, product images. One request.
  * ``https://deflorian.tirol/products/<handle>`` — server-rendered page; the 'ZUTATEN' accordion holds the ingredient
    list with allergens in capitals (metafield rich text). Only fetched by ``product()``/``fetch(ingredients=True)``,
    polite 1 req/s via the shared robots gate.
Ready meals = tags Fleischgerichte / Suppen / Knödel / Schlutzkrapfen, the savoury Zillertaler Kaskrapfen and the fruit
dumplings (Marillen-/Zwetschken-/Erdbeerknödel, sweet mains) — minus Fleischsugo (sauce), Milzschnitten (soup
garnish), Semmel-/Leberknödel (side/soup garnish), Probierpakete, pastries (Krapfen, Kiachl, Wuchteln, Gugelhupf),
sides (Sauerkraut, Eierspatzln, Erdäpfelblattln/-paunzen, Parmesan, Butterbrösel) and vouchers.
No nutrition table and no GTIN are published on the shop (never estimated); the same products are in MPreis with EAN.
Shipping (policies/shipping-policy, read 2026-10-25): Austria-wide only, deep-frozen with dry ice, delivery on
Thursdays; 14,99 € below 40 € basket, free from 40 €.
Photos: first product image (food photo or printed pack with dish photo); vision gate 2026-10-25 27/27 PASS.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://deflorian.tirol"
STORE = "Online: Deflorian"
PRODUCER = "Deflorian Tiefkühlspezialitäten GmbH, Hnr. 35b, 6069 Gnadenwald, Tirol (UID ATU64259769, LG Innsbruck)"
SHIPPING_EUR = 14.99
SHIPPING_NOTE = ("Versand nur innerhalb Österreichs, tiefgekühlt im Isolierkarton mit Trockeneis, Zustellung donnerstags; "
                 "14,99 € unter 40 € Warenkorb, ab 40 € versandkostenfrei (policies/shipping-policy)")
STORAGE = "tiefgekühlt (−18 °C)"
MEAL_TAGS = {"Fleischgerichte", "Suppen", "Knödel", "Schlutzkrapfen"}
EXCLUDE = re.compile(r"sugo|milzschnitt|semmelkn|leberkn|probierpaket|gutschein", re.I)
EXTRA = re.compile(r"zillertaler|marillenkn|zwetschkenkn|erdbeerkn", re.I)


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/products.json?limit=250", timeout=40).get("products", [])


def is_meal(sp: dict) -> bool:
    key = (sp.get("handle") or "") + " " + (sp.get("title") or "")
    if EXCLUDE.search(key):
        return False
    return bool(MEAL_TAGS & set(sp.get("tags") or [])) or bool(EXTRA.search(key))


def kind(sp: dict) -> str:
    tags = set(sp.get("tags") or [])
    if "Suppen" in tags: return "Suppe"
    if "Nachspeisen" in tags: return "süße Hauptspeise"
    if "Fleischgerichte" in tags: return "Fleischgericht"
    return "Teigware/Knödel"


def ingredients_from_html(page: str) -> str | None:
    i = page.find("ZUTATEN")
    if i < 0: return None
    j = page.find("metafield-rich_text_field", i)
    if j < 0: return None
    k = page.find("</div>", j)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", page[page.find(">", j) + 1:k])).replace("\xad", "").replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.)])", r"\1", t); t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"^Zutaten:\s*", "", t)
    return t or None


def page_ingredients(handle: str) -> str | None:
    try:
        return ingredients_from_html(get(f"{BASE}/products/{handle}", headers={"Accept": "text/html"}, raw=True, timeout=30).decode("utf-8", "replace"))
    except Exception:
        return None


def to_product(sp: dict, ingredients: str | None = None) -> Product:
    v = (sp.get("variants") or [{}])[0]
    price = float(v["price"]) if v.get("price") else None
    size = float(v["grams"]) if v.get("grams") else None
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    return Product(
        source="deflorian",
        store=STORE,
        name=(sp.get("title") or "").strip(),
        brand="Deflorian",
        price_eur=price,
        unit_price_eur=round(price / size * 100, 2) if price and size else None,
        unit="100 g" if price and size else None,
        size_g=size,
        nutrition_100g={},
        ean=v.get("barcode") or None,
        image_url=imgs[0] if imgs else None,
        producer=PRODUCER,
        origin="AT (handgemacht in Gnadenwald, Tirol lt. Shop)",
        category="Fertiggericht",
        source_url=f"{BASE}/products/{sp.get('handle')}",
        source_id=str(sp.get("id")),
        extra={
            "handle": sp.get("handle"),
            "pack": v.get("title"),
            "variants": [{"title": x.get("title"), "price": x.get("price"), "grams": x.get("grams"),
                          "available": x.get("available")} for x in (sp.get("variants") or [])],
            "available": bool(v.get("available")),
            "kind": kind(sp),
            "tags": sp.get("tags") or [],
            "description": _text(sp.get("body_html")),
            "ingredients": ingredients,
            "storage": STORAGE,
            "price_note": "Preis der kleinsten Packung inkl. MwSt. lt. Shopify-Storefront (EUR); Gewicht = Shopify-Variantengewicht",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(handle_id_or_url: str, shop: list[dict] | None = None, page_html: str | None = None) -> Product | None:
    k = handle_id_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    sp = next((p for p in (shop if shop is not None else store_products())
               if str(p.get("id")) == k or p.get("handle") == k), None)
    if not sp:
        return None
    ing = ingredients_from_html(page_html) if page_html is not None else page_ingredients(sp["handle"])
    return to_product(sp, ing)


class Deflorian(Adapter):
    id = "deflorian"
    store = STORE
    homepage = BASE
    notes = ("Live: public Shopify storefront of Deflorian Tiefkühlspezialitäten GmbH (Gnadenwald, Tirol): frozen "
             "Schlutzkrapfen, Knödel, Kaskrapfen, Gulasch/Curry/Rindsbraten, soups and fruit dumplings with price, pack, "
             "weight, availability, photo; ingredients from product pages; ships AT-wide (14,99 €, free from 40 €); "
             "no nutrition/GTIN on the shop")

    def fetch(self, category="ready-meals", limit=500, ingredients=True):
        out = []
        for sp in [p for p in store_products() if is_meal(p)][:limit]:
            out.append(to_product(sp, page_ingredients(sp["handle"]) if ingredients else None))
        return out

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if not is_meal(sp):
                continue
            hay = (sp.get("title", "") + " " + _text(sp.get("body_html")) + " " + " ".join(sp.get("tags") or [])).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp))
        return out[:limit]
