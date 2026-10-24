"""Wagyuhof Frischglas (wagyuhof.com) — Wagyuhof GmbH, Porstenberg 17, 3350 Haag (Mostviertel, NÖ), breeds Wagyu
cattle and sells its own shelf-stable heat-up jar meals ('Frischglas', 300 g, 'ohne Kühlen') online, shipped to AT + DE.

Source (public Shopify storefront, no login/cookies; robots.txt ``User-agent: *`` disallows only cart/checkout/account,
sort/filter collection URLs and recommendations):
  * ``https://wagyuhof.com/collections/frischglas/products.json`` — the storefront JSON: handle, title, price (EUR),
    availability, SKU, product images. One request.
  * ``https://wagyuhof.com/products/<handle>`` — server-rendered product page with 'Nährwerte pro 100g' (energy, fat,
    saturates, carbs, sugar, protein, salt), 'Zutaten' (allergens in capitals) and the jar size. One request per meal.
Ready meals = jars of collection 'Frischglas' minus sauces (Sugo, Jus), plain broth (Rindsuppe), '3+1 gratis' multipacks
and gift boxes. No GTIN published (variant barcode empty) → never guessed.
Shipping (wagyuhof.com/policies/shipping-policy, read 2026-10-24): AT + DE, Wed + Fri delivery; 14,90 € below 30 €,
9,90 € from 30 €, free from 150 €.
Operator (wagyuhof.com/policies/legal-notice): Wagyuhof GmbH, FN 478220s (LG St. Pölten), UID ATU72584759 (VIES valid
2026-10-24), LEI 98450053J99E55F43D03 (GLEIF, ISSUED), managing director Florian Irxenmayr.
Polite: 1 req/s via the shared http helper.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://wagyuhof.com"
STORE = "Online: Wagyuhof"
PRODUCER = "Wagyuhof GmbH, Porstenberg 17, 3350 Haag (FN 478220s, UID ATU72584759)"
SHIPPING_NOTE = ("Versand AT + DE (Mi/Fr): 14,90 € unter 30 €, 9,90 € ab 30 €, versandkostenfrei ab 150 € "
                 "lt. wagyuhof.com/policies/shipping-policy")
EXCLUDE = re.compile(r"sugo|\bjus\b|rindsuppe|rindssuppe|suppe\b|3-1-gratis|3\+1|box|geschenk|gutschein", re.I)
NUT = [("kcal", r"Energie:?\s*[\d.,]+\s*kJ\s*/\s*([\d.,]+)\s*kcal"),
       ("fat", r"Fett:?\s*([\d.,]+)\s*g"),
       ("satfat", r"ges[äa]ttigte\s+Fetts\w*:?\s*([\d.,]+)\s*g"),
       ("carbs", r"Kohlenhydrate:?\s*([\d.,]+)\s*g"),
       ("sugar", r"Zucker:?\s*([\d.,]+)\s*g"),
       ("protein", r"Eiwei(?:ß|ss):?\s*([\d.,]+)\s*g"),
       ("salt", r"Salz:?\s*([\d.,]+)\s*g")]


def _text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/collections/frischglas/products.json?limit=250", timeout=40).get("products", [])


def page(handle: str) -> str:
    return get(f"{BASE}/products/{handle}", headers={"Accept": "text/html"}, raw=True, timeout=40).decode("utf-8", "replace")


def is_meal(sp: dict) -> bool:
    return sp.get("product_type") == "Wagyu Frischglas" and not EXCLUDE.search((sp.get("handle") or "") + " " + (sp.get("title") or ""))


def parse_page(html: str) -> dict:
    t = _text(html)
    out = {"nutrition_100g": {}, "ingredients": None, "size_g": None}
    i = t.find("Nährwerte")
    if i >= 0:
        blk = t[i:i + 600]
        cut = blk.find("Zutaten")
        blk = blk[:cut] if cut > 0 else blk
        for k, rx in NUT:
            m = re.search(rx, blk, re.I)
            if m:
                out["nutrition_100g"][k] = float(m.group(1).replace(",", "."))
        j = t.find("Zutaten", i)
        if j >= 0:
            z = t[j + len("Zutaten"):j + 900]
            z = re.split(r"\s(?:Haltbarkeit|Zubereitung|Versandinformationen|Lagerung|Details:)\b", z)[0]
            out["ingredients"] = re.sub(r"^\s*(?:Wagyu [^:]{0,30}:)?\s*", "", z).strip() or None
    m = re.search(r"(\d{3})\s*g\s*(?:\"|„|“)?Frischglas", t)
    out["size_g"] = float(m.group(1)) if m else None
    return out


def to_product(sp: dict, html: str | None = None) -> Product:
    v = (sp.get("variants") or [{}])[0]
    price = float(v["price"]) if v.get("price") else None
    det = parse_page(html) if html else {"nutrition_100g": {}, "ingredients": None, "size_g": None}
    size = det["size_g"]
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    return Product(
        source="wagyuhof",
        store=STORE,
        name=(sp.get("title") or "").strip(),
        brand="Wagyuhof Frischglas",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
        size_g=size,
        nutrition_100g=det["nutrition_100g"],
        ean=(v.get("barcode") or None),
        image_url=imgs[0] if imgs else None,
        producer=PRODUCER,
        origin="AT (eigene Wagyu-Rinder, Haag NÖ lt. Shop)",
        category="Fertiggericht",
        source_url=f"{BASE}/products/{sp.get('handle')}",
        source_id=str(sp.get("id")),
        extra={
            "handle": sp.get("handle"),
            "sku": v.get("sku"),
            "available": bool(v.get("available")),
            "ingredients": det["ingredients"],
            "images": imgs,
            "storage": "Frischglas, haltbar ohne Kühlen lt. Shop",
            "price_note": "Preis je Glas lt. Shopify-Storefront (Markt AT, EUR)",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(handle_id_or_url: str, shop: list[dict] | None = None, html: str | None = None) -> Product | None:
    k = handle_id_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or p.get("handle") == k), None)
    if not sp:
        return None
    return to_product(sp, html if html is not None else page(sp["handle"]))


class Wagyuhof(Adapter):
    id = "wagyuhof"
    store = STORE
    homepage = BASE
    notes = ("Live: public Shopify storefront of Wagyuhof GmbH (Haag NÖ), collection 'Frischglas': shelf-stable 300 g jar "
             "meals (Gulasch, Ragout, Beuschel, Rouladen) with price, availability, packshots + nutrition/ingredients from "
             "the product page; ships AT+DE (14,90 €/<30 €, 9,90 €, free from 150 €); no GTIN; ~1+N requests")

    def fetch(self, category="ready-meals", limit=500):
        return [to_product(sp, page(sp["handle"])) for sp in store_products() if is_meal(sp)][:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if not is_meal(sp):
                continue
            hay = (sp.get("title", "") + " " + sp.get("handle", "") + " " + _text(sp.get("body_html", ""))).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp, page(sp["handle"])))
            if len(out) >= limit:
                break
        return out
