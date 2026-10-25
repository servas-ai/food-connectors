"""RegionAlles Joglland online shop (regionalles.com) — regional store + Shopify webshop in Waldbach-Mönichwald (Joglland,
Oststeiermark). Operator per Impressum: RegionALLES WB OG, Arzberg 51, 8253 Waldbach (FN 537480 m; UID ATU75793759 — EU VIES
valid 2026-10-25 'RegionALLES WB OG, Arzberg 51/1, AT-8253 Waldbach-Mönichwald'; GLEIF: no LEI).

Source (public, robots.txt allows /products*): Shopify ``/products.json?limit=250`` (one request) → ready meals in jars =
Gastwirtschaft Hold ('Holdi's' Gulasch, Chili con Carne, Chili sin Carne, Leberknödelsuppe; 0,427 l jar), Biohof
Krautgartner Bio-Putengulasch and Jobi (Forellengasthof Joglland, Rettenegg) Fischsuppe. Leberkäs im Glas (cold meat loaf),
pickled fish (Jobi Roller/Schorfe), sauces and noodles are excluded. No nutrition and no GTIN published → never estimated.
Shipping (FAQ): Austria-wide with Österreichische Post, chilled shipping possible at extra cost, free shipping from 79 €;
no minimum order value. Prices incl. jar deposit ('inkl. Pfandglas').
"""
from __future__ import annotations
import html as _html, json, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.regionalles.com"
STORE = "Online: RegionAlles Joglland"
OPERATOR = "RegionALLES WB OG, Arzberg 51, 8253 Waldbach-Mönichwald, Steiermark (FN 537480 m, UID ATU75793759)"
SHIPPING_NOTE = ("Post AG österreichweit (Kühlversand gegen Aufpreis), versandkostenfrei ab 79 €, kein Mindestbestellwert; "
                 "Selbstabholung Waldbach möglich; Preise inkl. Pfandglas")
MEALS = {"gulasch-im-glas", "chili-con-carne-im-glas", "holdis-chili-sin-carne-im-glas", "leberknodelsuppe-im-glas",
         "biohof-krautgartner-putengulasch", "jobi-fischsuppe"}
# vision gate 2026-10-25: Chili sin Carne uses the Chili con Carne packshot (label reads 'Chili con carne') → no photo
BAD_PHOTO = {"holdis-chili-sin-carne-im-glas"}
SIZE_ML = {"jobi-fischsuppe": 430.0}  # 'Nettofüllmenge 430 ml' on the packshot label


def _clean(s: str) -> str:
    s = _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def products_json() -> list[dict]:
    return json.loads(get(f"{BASE}/products.json?limit=250", raw=True, timeout=40))["products"]


def parse(x: dict) -> Product | None:
    h = x.get("handle")
    if h not in MEALS:
        return None
    v = (x.get("variants") or [{}])[0]
    price = float(v["price"]) if v.get("price") else None
    desc = _clean(x.get("body_html"))
    m = re.search(r"Füllmenge von ([\d,]+) ?lt", desc)
    size = round(float(m.group(1).replace(",", ".")) * 1000, 1) if m else SIZE_ML.get(h)
    prod = re.search(r"Produzent: (.+?)(?: Das | Die | Schnelle | Der |$)", desc)
    img = None if h in BAD_PHOTO or not x.get("images") else x["images"][0]["src"].split("?")[0]
    return Product(
        source="regionalles", store=STORE, name=_html.unescape(x["title"]).replace('"', "").strip(), brand=x.get("vendor"),
        price_eur=price, unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="l" if price and size else None, size_g=size, nutrition_100g={}, ean=None, image_url=img,
        producer=prod.group(1).strip() if prod else x.get("vendor"), category="Fertiggericht",
        source_url=f"{BASE}/products/{h}", source_id=str(x.get("id")),
        extra={"handle": h, "vendor": x.get("vendor"), "in_stock": bool(v.get("available")), "description": desc[:600],
               "bio": "bio" in [t.lower() for t in x.get("tags", [])], "veg": "sin carne" in h or "vegetarisch" in desc.lower(),
               "price_note": "Preis inkl. USt. und Pfandglas lt. Shopify products.json", "shipping_note": SHIPPING_NOTE})


def all_products(items: list[dict] | None = None) -> list[Product]:
    items = items if items is not None else products_json()
    return [p for p in (parse(x) for x in items) if p]


def product(handle_or_url: str, items: list[dict] | None = None) -> Product | None:
    h = handle_or_url.strip().rstrip("/").split("/")[-1]
    return next((p for p in all_products(items) if p.extra["handle"] == h), None)


class RegionAlles(Adapter):
    id = "regionalles"
    store = STORE
    homepage = BASE
    notes = ("Live: RegionAlles Joglland (RegionALLES WB OG, Waldbach-Mönichwald Stmk; FN 537480 m, UID ATU75793759) — "
             "Shopify products.json: 6 jar ready meals (Holdi's Gulasch/Chili con/sin Carne/Leberknödelsuppe 0,427 l, "
             "Krautgartner Bio-Putengulasch, Jobi Fischsuppe 430 ml); no nutrition/GTIN; Post AT, free from 79 €")

    def fetch(self, category="ready-meals", limit=50):
        return all_products()[:limit]

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        return [p for p in all_products() if all(w in f"{p.name} {p.extra.get('description')}".lower() for w in words)][:limit]
