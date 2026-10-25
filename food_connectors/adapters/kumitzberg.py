"""Kumitzberg (kumitzberg.at) — online shop of Großarler Genuss GmbH, Sonneggweg 1, 5611 Großarl (Pongau,
Salzburg), butcher/deli products incl. chilled heat-up dishes (Rehragout im Glas, pre-baked Knödel, fully roasted
Schweinsbraten, pre-cooked Sous-Vide Spareribs), shipped chilled with DHL within Austria (and EU).

Source (public Shopify storefront, no login/cookies; robots.txt ``User-agent: *`` ``Allow: /``):
  * ``https://kumitzberg.at/products.json?limit=250`` — storefront JSON: handle, title, product_type, price (EUR incl.
    USt), availability, grams, SKU, images. One request.
  * ``https://kumitzberg.at/products/<handle>`` — server-rendered page with 'Zutaten' and 'Nährwerte je 100 g' where the
    shop publishes them. One request per meal (shared polite http helper).
Ready meals = product_type 'Fertiggericht' or 'Knödel', plus 'fertig gebraten' roasts and the pre-baked Kaspressknödel
(typed 'Suppeneinlage' but sold 'gebacken & servierfertig'); excluded: Wild-Leberpasteten (spreads), Leberknödel (soup
garnish), raw meat, sausages, spreads, gift boxes. GTIN: empty in products.json but published on ``/products/<handle>.json`` → read via ``shopify_gtin``.
Nutrition only as printed on the product page (Rehragout, Schweinsbraten 'ca.', Spareribs); missing → empty.
Shipping (kumitzberg.at/policies/shipping-policy, read 2026-10-25): DHL chilled, dispatch Tue + Thu, Austria 9,90 €,
free from 95 €; DE 10,90 € (free from 110 €); other EU 12,90–14,90 €.
Operator (kumitzberg.at/policies/legal-notice): Großarler Genuss GmbH, Sonneggweg 1, 5611 Großarl, FN 473130f
(LG Salzburg), UID ATU72344714 (EU VIES valid 2026-10-25, same name/address), managing directors Thomas Ammerer,
Jürgen Höllmüller; EU approval number AT 50774 EU; no LEI (GLEIF 0 records 2026-10-25).
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product
from .shopify_gtin import gtin, enrich, drop_shared

BASE = "https://kumitzberg.at"
STORE = "Online: Kumitzberg"
PRODUCER = "Großarler Genuss GmbH (Kumitzberg), Sonneggweg 1, 5611 Großarl, Salzburg (FN 473130f, LG Salzburg; UID ATU72344714)"
SHIPPING_NOTE = ("Gekühlter DHL-Versand (Di/Do), Österreich 9,90 €, versandkostenfrei ab 95 €; DE 10,90 € (frei ab 110 €) "
                 "lt. kumitzberg.at/policies/shipping-policy")
MEAL_TYPES = {"Fertiggericht", "Knödel"}
INCLUDE = re.compile(r"fertig gebraten|kaspressknödel", re.I)
EXCLUDE = re.compile(r"pastete|leberknödel|aufstrich|genussbox|paket|gutschein", re.I)
NUT = [("kcal", r"([\d.,]+)\s*kcal"),
       ("fat", r"Fett:?\s*([\d.,]+)\s*g"),
       ("satfat", r"ges[äa]ttigte\s+Fetts\w*:?\s*([\d.,]+)\s*g"),
       ("carbs", r"Kohlenhydrate:?\s*([\d.,]+)\s*g"),
       ("sugar", r"Zucker:?\s*([\d.,]+)\s*g"),
       ("protein", r"Eiwei(?:ß|ss):?\s*([\d.,]+)\s*g"),
       ("salt", r"Salz:?\s*([\d.,]+)\s*g")]


def _text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).replace("\xa0", " ").replace("\u202f", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/products.json?limit=250", timeout=40).get("products", [])


def page(handle: str) -> str:
    return get(f"{BASE}/products/{handle}", raw=True, headers={"Accept": "text/html"}).decode("utf-8", "replace")


def is_meal(sp: dict) -> bool:
    t = (sp.get("title") or "") + " " + (sp.get("handle") or "")
    if EXCLUDE.search(t):
        return False
    return sp.get("product_type") in MEAL_TYPES or bool(INCLUDE.search(t))


def size_g(sp: dict) -> tuple[float | None, bool]:
    """(grams, approximate) from variant weight, else from the title ('380 g', 'ca. 1,2 kg', '1kg')."""
    v = (sp.get("variants") or [{}])[0]
    t = sp.get("title") or ""
    m = re.search(r"(ca\.\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g)\b", t)
    approx = bool(m and m.group(1))
    if v.get("grams") and 0 < v["grams"] < 50000:
        return float(v["grams"]), approx
    if m:
        n = float(m.group(2).replace(",", "."))
        return (n * 1000 if m.group(3) == "kg" else n), approx
    return None, False


def parse_page(html_text: str) -> dict:
    t = _text(html_text)
    z = re.search(r"Zutaten:?\s+(.*?)\s+(?:Nährwerte|Verpackungsinhalt|Unter Schutzatmosph|Verpackt unter|Dieses Produkt teilen)", t)
    n = re.search(r"Nährwert\w*\s+(.*?)(?:Customer Reviews|Dieses Produkt teilen|$)", t)
    nut, approx = {}, False
    if n and re.search(r"kcal", n.group(1)):
        seg = n.group(1)
        approx = bool(re.search(r"ca\.\s*[\d.,]+\s*kcal", seg))
        for k, rx in NUT:
            m = re.search(rx, seg)
            if m and not re.search(r"<\s*$", seg[:m.start(1)]):
                nut[k] = float(m.group(1).replace(".", "").replace(",", ".")) if k == "kcal" else float(m.group(1).replace(",", "."))
    return {"ingredients": z.group(1).strip().rstrip(".") if z else None, "nutrition": nut, "nutrition_approx": approx}


def to_product(sp: dict, html_text: str | None = None) -> Product:
    v = (sp.get("variants") or [{}])[0]
    price = float(v["price"]) if v.get("price") else None
    size, approx = size_g(sp)
    d = parse_page(html_text) if html_text else {"ingredients": None, "nutrition": {}, "nutrition_approx": False}
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    name = re.split(r"\s+[|–]\s+|\s+-\s+", sp.get("title") or "")[0].strip()
    name = re.sub(r"\s+(?:ca\.\s*)?\d+(?:[.,]\d+)?\s*(?:kg|g)$", "", name)
    if re.search(r"fertig gebraten", sp.get("title") or "", re.I) and "gebraten" not in name:
        name += ", fertig gebraten"
    return Product(
        source="kumitzberg", store=STORE, name=name, brand="Kumitzberg",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
        size_g=size, nutrition_100g=d["nutrition"], ean=gtin(v),
        image_url=imgs[0] if imgs else None, producer=PRODUCER, category="Fertiggericht",
        source_url=f"{BASE}/products/{sp.get('handle')}", source_id=str(sp.get("id")),
        extra={"handle": sp.get("handle"), "title": sp.get("title"), "product_type": sp.get("product_type"),
               "sku": v.get("sku"), "available": v.get("available"), "size_approx": approx,
               "ingredients": d["ingredients"], "nutrition_approx": d["nutrition_approx"], "images": imgs,
               "description": _text(sp.get("body_html") or "")[:600],
               "price_note": "Preis je Packung inkl. USt lt. Shopify products.json", "shipping_note": SHIPPING_NOTE},
    )


def product(handle_or_url: str, shop: list[dict] | None = None, html_text: str | None = None) -> Product | None:
    k = handle_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    sp = next((p for p in (shop if shop is not None else store_products()) if p.get("handle") == k or str(p.get("id")) == k), None)
    if not sp or not is_meal(sp):
        return None
    if shop is None:
        enrich(BASE, sp)
    return to_product(sp, html_text if html_text is not None else page(sp["handle"]))


class Kumitzberg(Adapter):
    id = "kumitzberg"
    store = STORE
    homepage = BASE
    notes = ("Live: public Shopify products.json + product pages of Kumitzberg (Großarler Genuss GmbH, Großarl, Sbg): "
             "chilled heat-up meals (Rehragout im Glas, Tiroler-/Kaspressknödel, Schweinsbraten fertig gebraten, Sous-Vide "
             "Spareribs) with price, availability, ingredients and nutrition where printed; DHL AT 9,90 €, free from 95 €; GTIN from per-product JSON")

    def fetch(self, category="ready-meals", limit=500):
        return drop_shared([to_product(enrich(BASE, sp), page(sp["handle"])) for sp in store_products() if is_meal(sp)][:limit])

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = [sp for sp in store_products() if is_meal(sp)
               and all(w in ((sp.get("title") or "") + " " + _text(sp.get("body_html") or "")).lower() for w in words)]
        return [to_product(sp, page(sp["handle"])) for sp in out[:limit]]
