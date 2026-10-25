"""Fleischhauerei Thaller (fleischhauerei-thaller.at) — family butcher in Markt Hartmannsdorf (Bezirk
Weiz, Steiermark, 'seit 1898') selling its own chilled heat-up jar dishes ('Speisen im Glas') online with
Austrian Post shipping.

Source (public, no login/cookies; robots.txt ``User-agent: *`` disallows only wp-admin, WooCommerce
upload/log folders and ``?add-to-cart=`` URLs):
  * WooCommerce Store API ``https://fleischhauerei-thaller.at/wp-json/wc/store/v1/products?per_page=100`` —
    the JSON the shop front-end uses: name, price (minor units, EUR incl. 10 % MwSt.), stock, categories,
    images and the description with 'Zutaten: …', 'NNNg per Glas', shelf life and preparation.
Ready meals = category 'Speisen im Glas' minus clear broth (Rindssuppe: water, beef, bones, salt — a
stock, like Rinderbrühe/Rindsuppe elsewhere) and raw Leberkäse/Käseleberkäse to bake (45 min at 130 °C,
a sausage product listed under 'Wurstwaren'). Currently 1 meal: Rindsgulasch im Glas 350 g.
No nutrition and no GTIN are published → never estimated.
Shipping (fleischhauerei-thaller.at/versandarten/, read 2026-10-25): only within Austria via Österreichische
Post (Next Day for fresh goods), dispatch Tue/Wed; 18,90 € up to 150 €, 10,90 € up to 250 €, free from 250 €.
Operator (fleischhauerei-thaller.at/impressum/): Fleischhauerei Thaller – Eduard Thaller, Hauptstraße 34,
8311 Markt Hartmannsdorf, UID ATU74028946 (EU VIES valid 2026-10-25, name 'Thaller Eduard Franz',
Hauptstraße 34/2, 8311 Markt Hartmannsdorf); sole trader, no Firmenbuch number published.
Polite: one request per call.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://fleischhauerei-thaller.at"
STORE = "Online: Fleischhauerei Thaller"
PRODUCER = "Fleischhauerei Thaller – Eduard Thaller, Hauptstraße 34, 8311 Markt Hartmannsdorf (UID ATU74028946)"
SHIPPING_NOTE = ("Versand nur innerhalb Österreichs mit der Österreichischen Post (Next Day für Frischware, Versand Di/Mi); "
                 "18,90 € bis 150 €, 10,90 € bis 250 €, versandkostenfrei ab 250 € lt. fleischhauerei-thaller.at/versandarten/")
CATEGORY = "Speisen im Glas"
EXCLUDE = re.compile(r"suppe|brühe|fond\b|leberk[äa]se|aufstrich|schmalz|streichwurst|gutschein", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def is_meal(sp: dict) -> bool:
    cats = [_html.unescape(c.get("name", "")) for c in (sp.get("categories") or [])]
    if CATEGORY not in cats:
        return False
    return not EXCLUDE.search(_html.unescape(sp.get("name") or "") + " " + (sp.get("slug") or ""))


def parse_description(desc_html: str) -> dict:
    t = _clean(desc_html)
    z = re.search(r"Zutaten:\s*(?:Zutaten:\s*)?(.*?)\s*\d+\s*(?:g|ml)\s*per Glas", t)
    s = re.search(r"(\d+)\s*(g|ml)\s*per Glas", t)
    h = re.search(r"Haltbarkeit:\s*Bei\s*([\d\s°C–-]+?):\s*([\d ]+)\s*Tage", t)
    p = re.search(r"Zubereitung\s+(.*?\.)\s+([^.]*?\.)", t)
    return {
        "ingredients": z.group(1).strip().rstrip(".") if z else None,
        "size": float(s.group(1)) if s else None,
        "size_unit": s.group(2) if s else None,
        "storage": f"gekühlt {h.group(1).strip()}, {h.group(2).replace(' ', '')} Tage haltbar" if h else None,
        "preparation": (p.group(1) + " " + p.group(2)).strip() if p else None,
    }


def to_product(sp: dict) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    d = parse_description(sp.get("description") or "")
    size = d["size"] if d["size_unit"] == "g" else None
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    return Product(
        source="thaller",
        store=STORE,
        name=_html.unescape(sp.get("name") or "").strip(),
        brand="Fleischhauerei Thaller",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
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
            "ingredients": d["ingredients"],
            "storage": d["storage"],
            "preparation": d["preparation"],
            "images": imgs,
            "price_note": "Preis je Glas inkl. 10 % MwSt. lt. WooCommerce Store API",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(id_slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or p.get("slug") == k), None)
    return to_product(sp) if sp and is_meal(sp) else None


class Thaller(Adapter):
    id = "thaller"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of Fleischhauerei Thaller (Markt Hartmannsdorf, Stmk): 'Speisen im Glas' "
             "heat-up jar meals (Rindsgulasch 350 g), price incl. MwSt., stock, ingredients, shelf life, packshots; "
             "broth and raw Leberkäse excluded; Post AT-wide 18,90 €/10,90 €, free from 250 €; no nutrition/GTIN; 1 request per call")

    def fetch(self, category="ready-meals", limit=500):
        return [to_product(sp) for sp in store_products() if is_meal(sp)][:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if not is_meal(sp):
                continue
            hay = (sp.get("name", "") + " " + sp.get("slug", "") + " " + _clean(sp.get("description", ""))).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp))
        return out[:limit]
