"""Bernos Tauernwild (bernos.at) — 'Bernos Wildkammer' of hunter/butcher Berno Mühlburger in Oberdrum,
Osttirol, selling his own heat-up wild-game jar dishes (Reh, Hirsch, Gams from the Hohen Tauern) online.

Source (public, no login/cookies; robots.txt (Yoast) ``User-agent: *`` ``Disallow:`` — everything allowed):
  * WooCommerce Store API ``https://www.bernos.at/wp-json/wc/store/v1/products?per_page=100`` — the JSON
    the shop front-end uses: name, price (minor units, EUR incl. MwSt.), stock, images, short description
    with 'Glasinhalt NNNg', meat share and 'ZUTATEN: …', long description with preparation.
The shop sets no categories, so ready meals = products whose short description says 'Glasinhalt' minus
Wildsugo (a pasta sauce). Henkele (air-dried meat) and the 'Taurer' Dauerwürste have no 'Glasinhalt' and
are cold cuts. Currently 4 meals 290 g: Rehragout, Hirschgulasch, Gamseintopf, Gulaschsuppe vom Wild
(its long text also says 'Glasinhalt 300 ml'; the short description's 290 g is used).
No nutrition and no GTIN are published → never estimated.
Shipping (bernos.at/versandarten/, read 2026-10-25): Österreich 5,60 €, Italien/Deutschland 8,50 €.
Operator (bernos.at/impressum/): Bernos Wildkammer, Inhaber Berno Mühlburger, Oberdrum 20, A-9903
(Oberlienz), Tel. 0664/5419954, info@bernos.at, UID ATU68061919 (EU VIES valid 2026-10-25, name
'Mühlburger Berno Alois', Oberdrum 20, AT-9903 Oberlienz); sole trader, no Firmenbuch number published.
Polite: one request per call.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.bernos.at"
STORE = "Online: Bernos Tauernwild"
PRODUCER = "Bernos Wildkammer – Berno Mühlburger, Oberdrum 20, 9903 Oberlienz, Osttirol (UID ATU68061919)"
SHIPPING_NOTE = "Versandkosten Österreich 5,60 €, Italien und Deutschland 8,50 € lt. bernos.at/versandarten/"
EXCLUDE = re.compile(r"sugo|sauce|soße|fond\b|brühe|henkele|taurer|wurst|gutschein|balsam", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def _slug(sp: dict) -> str:
    return (sp.get("permalink") or "").rstrip("/").split("/")[-1]


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def is_meal(sp: dict) -> bool:
    if not re.search(r"Glasinhalt", _clean(sp.get("short_description") or "")):
        return False
    return not EXCLUDE.search(_html.unescape(sp.get("name") or "") + " " + _slug(sp))


def parse_short(sd_html: str) -> dict:
    t = _clean(sd_html)
    s = re.search(r"Glasinhalt:?\s*(\d+)\s*(g|ml)", t)
    m = re.search(r"((?:[\w,\- ]+)?fleischanteil:\s*\d+\s*%)", t, re.I)
    z = re.search(r"ZUTATEN:\s*(.*?)\s*keine Geschmacksverst", t)
    return {
        "size": float(s.group(1)) if s else None,
        "size_unit": s.group(2) if s else None,
        "meat_share": m.group(1).strip() if m else None,
        "ingredients": z.group(1).strip().rstrip(".") if z else None,
        "free_from": "keine Geschmacksverstärker, Konservierungsstoffe, Farbstoffe, Verdickungsmittel; glutenfrei" if "Gluten frei" in t else None,
    }


def to_product(sp: dict) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    d = parse_short(sp.get("short_description") or "")
    size = d["size"] if d["size_unit"] == "g" else None
    long = _clean(sp.get("description") or "")
    prep = re.search(r"SO SCHMECKTS AM BESTEN:\s*(.*?)(?:\s*…|$)", long)
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    return Product(
        source="bernos",
        store=STORE,
        name=_html.unescape(sp.get("name") or "").strip(),
        brand="Bernos Tauernwild",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None,
        size_g=size,
        nutrition_100g={},
        ean=None,
        image_url=imgs[0] if imgs else None,
        producer=PRODUCER,
        category="Fertiggericht",
        source_url=sp.get("permalink") or f"{BASE}/produkt/{_slug(sp)}/",
        source_id=str(sp.get("id")),
        extra={
            "wc_id": sp.get("id"),
            "slug": _slug(sp),
            "in_stock": sp.get("is_in_stock"),
            "ingredients": d["ingredients"],
            "meat_share": d["meat_share"],
            "free_from": d["free_from"],
            "preparation": prep.group(1).strip() if prep else None,
            "images": imgs,
            "price_note": "Preis je Glas inkl. MwSt. lt. WooCommerce Store API",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(id_slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or _slug(p) == k), None)
    return to_product(sp) if sp and is_meal(sp) else None


class Bernos(Adapter):
    id = "bernos"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of Bernos Tauernwild (Berno Mühlburger, Oberdrum/Oberlienz, Osttirol): "
             "4 heat-up wild-game jar meals 290 g (Rehragout, Hirschgulasch, Gamseintopf, Gulaschsuppe vom Wild), price incl. MwSt., "
             "stock, meat share, ingredients, packshots; Wildsugo and cold cuts excluded; AT shipping 5,60 €; no nutrition/GTIN; 1 request per call")

    def fetch(self, category="ready-meals", limit=500):
        return [to_product(sp) for sp in store_products() if is_meal(sp)][:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if not is_meal(sp):
                continue
            hay = (sp.get("name", "") + " " + _slug(sp) + " " + _clean(sp.get("short_description", "")) + " " + _clean(sp.get("description", ""))).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp))
        return out[:limit]
