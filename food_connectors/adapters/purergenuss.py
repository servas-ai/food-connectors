"""Purer Genuss (purer-genuss.at) — own webshop of the Burgenland Wild-im-Glas brand 'Schüsseltrieb Manufaktur'
(venison from Burgenland hunting associations, processed by Fleischerei Hatwagner, cooked at Weinstube Szemes in
Pinkafeld). Shop operator per Impressum: 'Weinstube Familienbetrieb Szemes, Inhaber Philipp Szemes'; company per
szemes.net Impressum: Szemes GmbH, Hauptstraße 33, 7423 Pinkafeld, Bezirk Oberwart, Burgenland (FN 660812 h, LG Eisenstadt;
UID ATU82450358, EU VIES valid 2026-10-25 with the same name/address; GLEIF 0 hits → no LEI).

Source (public, no login/cookies; robots.txt disallows only wp-admin, WooCommerce upload/log folders and add-to-cart URLs):
  * WooCommerce Store API ``/wp-json/wc/store/v1/products?per_page=100`` — name, price (minor units, EUR incl. MwSt.),
    stock, category, 'Vegetarisch' attribute, packshot. One request per fetch.
Ready meals = category 'Schüsseltrieb' minus sauces (Wild Jus = Saucenbasis, Wildsugo). GINeins gin is not food → excluded.
The shop publishes no description, ingredients, nutrition, GTIN or net fill weight (only a WooCommerce shipping weight
'Gewicht 0,4 kg' on product pages) → size_g/nutrition/ean stay empty, never estimated.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.purer-genuss.at"
STORE = "Online: Purer Genuss (Schüsseltrieb)"
BRAND = "Schüsseltrieb Manufaktur"
PRODUCER = ("Schüsseltrieb Manufaktur — Szemes GmbH (Weinstube Szemes), Hauptstraße 33, 7423 Pinkafeld, Burgenland "
            "(FN 660812 h, UID ATU82450358) mit Fleischerei Hatwagner, Oberpullendorf")
SHIPPING_NOTE = ("Versandkosten/Liefergebiet nicht veröffentlicht (nur im Warenkorb) → leer; Abholung in Pinkafeld nach "
                 "telefonischer Vereinbarung lt. szemes.net")
CATEGORY = "Schüsseltrieb"
EXCLUDE = re.compile(r"\bjus\b|sugo|gin", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def _name(sp: dict) -> str:
    return _html.unescape(sp.get("name") or "").strip()


def _slug(sp: dict) -> str:
    return sp.get("slug") or (sp.get("permalink") or "").rstrip("/").split("/")[-1]


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def is_meal(sp: dict) -> bool:
    cats = {c.get("name") for c in sp.get("categories") or []}
    return CATEGORY in cats and not EXCLUDE.search(_name(sp) + " " + _slug(sp))


def _attr(sp: dict, name: str):
    for a in sp.get("attributes") or []:
        if a.get("name") == name:
            return ", ".join(t.get("name") for t in a.get("terms") or [])
    return None


def to_product(sp: dict) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    veg = _attr(sp, "Vegetarisch")
    return Product(
        source="purergenuss", store=STORE, name=_name(sp), brand=BRAND, price_eur=price,
        unit_price_eur=None, unit=None, size_g=None, nutrition_100g={}, ean=None,
        image_url=imgs[0] if imgs else None, producer=PRODUCER, category="Fertiggericht",
        source_url=sp.get("permalink") or f"{BASE}/product/{_slug(sp)}/", source_id=str(sp.get("id")),
        extra={"wc_id": sp.get("id"), "slug": _slug(sp), "in_stock": sp.get("is_in_stock"),
               "purchasable": sp.get("is_purchasable"), "categories": [c.get("name") for c in sp.get("categories") or []],
               "vegetarian": None if veg is None else veg.lower() == "ja", "images": imgs,
               "price_note": "Preis je Glas inkl. MwSt. lt. WooCommerce Store API, zzgl. Versand",
               "size_note": "keine Füllmenge veröffentlicht (Produktseite nennt nur Versandgewicht 0,4 kg) → leer",
               "shipping_note": SHIPPING_NOTE})


def all_products(shop: list[dict] | None = None) -> list[Product]:
    return [to_product(sp) for sp in (shop if shop is not None else store_products()) if is_meal(sp)]


def product(id_slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or _slug(p) == k), None)
    return to_product(sp) if sp and is_meal(sp) else None


class PurerGenuss(Adapter):
    id = "purergenuss"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of purer-genuss.at (Schüsseltrieb Manufaktur, Szemes GmbH Pinkafeld, "
             "Burgenland; FN 660812 h): Wild im Glas ready meals (Ragouts, Braten, Beuschel, Chili, Wildsuppe) with price "
             "incl. MwSt., stock, packshot; Wild Jus/Wildsugo (sauces) and GINeins gin excluded; no nutrition, GTIN or "
             "net weight published; shipping fee not published; 1 request")

    def fetch(self, category="ready-meals", limit=500):
        return all_products()[:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            hay = (_name(sp) + " " + _slug(sp) + " " + _clean(sp.get("short_description", "")) + " " + _clean(sp.get("description", ""))).lower()
            if is_meal(sp) and all(w in hay for w in words) and len(out) < limit:
                out.append(to_product(sp))
        return out
