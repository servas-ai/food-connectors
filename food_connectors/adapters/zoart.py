"""zoart — Sous Vide Fertiggerichte vom Schwein (sous-vide-fertiggerichte.at, also zoart.at): sous-vide pre-cooked
Styrian pork dishes from the own pig farm. Operator per Impressum/VIES: Barbara Fink KG, Oberrettenbach 19,
8212 Gersdorf an der Feistritz (Pischelsdorf am Kulm), Steiermark (FN 431088 d, LG für ZRS Graz; UID ATU69421556 —
EU VIES valid 2026-10-25, name 'Barbara Fink KG', address 'Oberrettenbach 19, AT-8213 Gersdorf/Feistritz';
GLEIF: no LEI). Unternehmensgegenstand Schweinemast und Ackerbau.

Source (public, no login/cookies; robots.txt disallows only wp-admin and WooCommerce log/upload folders):
  * WooCommerce Store API ``/wp-json/wc/store/v1/products?per_page=100`` — name, price (minor units, EUR incl. 10 %
    MwSt.), stock, packshot, description with the pack size ('Gesamtmenge: 550g/Packung', '1300g', '700g / 1300g').
  * variable products (Gewicht 700 g/1300 g, 500 g/1000 g) → one request per variation ``/products/<variation id>``
    for the variant price (1 req/s polite gate).
Ready meals = all sous-vide dishes minus Bratensaft/Jus (sauce) and Zunge (sold as Vorspeise/Jause cold cut).
No nutrition, ingredients list or GTIN published → empty, never estimated.
Shipping (Verpackung & Versand): chilled Naturkarton with paper icepacks via Österreichische Post within 24 h,
orders Mon–Thu by 10:00 delivered Tue–Fri; 12,00 € below 100 €, free from 100 €; pick-up at Rosy's Abholstationen.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.sous-vide-fertiggerichte.at"
STORE = "Online: Sous Vide Fertiggerichte (zoart)"
BRAND = "zoart Sous Vide"
PRODUCER = "Barbara Fink KG, Oberrettenbach 19, 8212 Gersdorf an der Feistritz, Steiermark (FN 431088 d, UID ATU69421556)"
SHIPPING_NOTE = ("gekühlt im Naturkarton mit Icepacks, Österreichische Post innerhalb 24 h (Zustellung Di–Fr); "
                 "12,00 € unter 100 €, versandkostenfrei ab 100 €")
SHIPPING_AT = 12.0
EXCLUDE = re.compile(r"bratensaft|\bjus\b|zunge", re.I)
_Q = re.compile(r"(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l)\b", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def _name(sp: dict) -> str:
    return _html.unescape(sp.get("name") or "").replace("\u2013", "–").strip()


def _slug(sp: dict) -> str:
    return sp.get("slug") or (sp.get("permalink") or "").rstrip("/").split("/")[-1]


def _qty(s: str):
    m = _Q.search(s or "")
    if not m:
        return None, None
    v = float(m.group(1).replace(",", "."))
    u = m.group(2).lower()
    return (v * 1000 if u in ("kg", "l") else v), ("ml" if u in ("ml", "l") else "g")


def _price(sp: dict):
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    return int(pr["price"]) / 10 ** mu if pr.get("price") else None


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def variation(vid) -> dict:
    return get(f"{BASE}/wp-json/wc/store/v1/products/{vid}", timeout=40)


def is_meal(sp: dict) -> bool:
    return bool(sp) and not EXCLUDE.search(_name(sp) + " " + _slug(sp))


def pack_text(sp: dict) -> str:
    d = _clean(sp.get("description"))
    d = d.split("exkl. Versand*", 1)[-1]
    return d.split("Bestellung – Versand", 1)[0].strip()


def to_product(sp: dict, var: dict | None = None) -> Product:
    txt = pack_text(sp)
    size, unit, vlabel = None, None, None
    if var is not None:
        vlabel = (var.get("variation") or "").split(":", 1)[-1].strip()
        size, unit = _qty(vlabel)
        price = _price(var)
    else:
        head = txt.split("–", 1)[0]
        size, unit = _qty(head.replace("Gesamtmenge:", ""))
        price = _price(sp)
    pieces = re.search(r"(\d+)\s*St\s?ück|(\d+)\s*Stk|mit (drei|zwei) Rouladen", txt)
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    name = _name(sp) + (f" {vlabel}" if vlabel else "")
    meat = re.search(r"davon\s+(\d+)\s*g\s+Fleisch", txt)
    return Product(
        source="zoart", store=STORE, name=name, brand=BRAND, price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit=("l" if unit == "ml" else "kg") if price and size else None, size_g=size, nutrition_100g={}, ean=None,
        image_url=imgs[0] if imgs else None, producer=PRODUCER, origin="AT (Steiermark, eigene Schweinemast)",
        category="Fertiggericht", source_url=(var or sp).get("permalink") or f"{BASE}/produkt/{_slug(sp)}/",
        source_id=str((var or sp).get("id")),
        extra={"wc_id": sp.get("id"), "variation_id": var.get("id") if var else None, "variant": vlabel,
               "slug": _slug(sp), "in_stock": (var or sp).get("is_in_stock"), "size_unit": unit,
               "meat_g": float(meat.group(1)) if meat else None,
               "pieces_note": pieces.group(0) if pieces else None, "description": txt[:600],
               "prep": "sous vide vorgegart; im Backrohr/am Grill bzw. in der Pfanne fertig garen oder erhitzen (lt. Produktseite)",
               "price_note": "inkl. 10 % MwSt., inkl. Verpackung, exkl. Versand lt. Produktseite",
               "shipping_note": SHIPPING_NOTE, "packaging": "Glas" if "glück" in _name(sp).lower() else "Vakuumbeutel"})


def expand(sp: dict, var_get=variation) -> list[Product]:
    if not is_meal(sp):
        return []
    vs = sp.get("variations") or []
    if not vs:
        return [to_product(sp)]
    return [to_product(sp, var_get(v["id"])) for v in vs]


def all_products(shop: list[dict] | None = None, var_get=variation) -> list[Product]:
    out = []
    for sp in (shop if shop is not None else store_products()):
        out += [p for p in expand(sp, var_get) if p.price_eur]
    return out


def product(id_slug_or_url: str, shop: list[dict] | None = None, var_get=variation) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    shop = shop if shop is not None else store_products()
    for sp in shop:
        if str(sp.get("id")) == k or _slug(sp) == k:
            ps = expand(sp, var_get)
            return ps[0] if ps else None
        for v in sp.get("variations") or []:
            if str(v["id"]) == k and is_meal(sp):
                return to_product(sp, var_get(v["id"]))
    return None


class Zoart(Adapter):
    id = "zoart"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of sous-vide-fertiggerichte.at (zoart, Barbara Fink KG, Gersdorf an der "
             "Feistritz, Stmk; FN 431088 d): sous-vide pre-cooked Styrian pork dishes (Stelzen, Schweinsbraten, Bauch, "
             "Spareribs, Rouladen, Gulasch im Glas, Pulled Pork) incl. weight variants, price incl. 10 % MwSt., stock, "
             "packshot; Bratensaft (sauce) and Zunge (Jause) excluded; no nutrition/GTIN; Post chilled 12 €, free from 100 €")

    def fetch(self, category="ready-meals", limit=500):
        return all_products()[:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            hay = (_name(sp) + " " + _slug(sp) + " " + pack_text(sp)).lower()
            if is_meal(sp) and all(w in hay for w in words):
                out += expand(sp)
            if len(out) >= limit:
                break
        return out[:limit]
