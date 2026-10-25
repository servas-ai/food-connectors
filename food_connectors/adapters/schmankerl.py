"""Schmankerl Österreich (schmankerl-oesterreich.at) — online delicatessen reseller ('Salzburg Spezialitäten') of
Innviertel/Austrian regional products, shipped chilled to AT, DE, IT and the EU. Operator per Impressum/AGB:
Pamela Plüschke – Salzburg Spezialitäten (Einzelunternehmen), Wenigaschau 1, 5143 Feldkirchen, Austria; Steuernummer
232/3461; no UID, no Firmenbuch number published; GLEIF: no LEI (2026-10-25).

Source (public Shopify storefront, no login/cookies; robots.txt = Shopify default, disallows only cart/checkout/account
and sort/filter collection URLs): ``/products.json?limit=250`` — one request, all products with title, price (EUR incl.
MwSt.), availability, images and the product description (``body_html``) carrying 'Inhalt', 'Zutaten', 'Allergene',
'Herkunft' and 'Lagerung'.
Ready meals kept: chilled hand-made Knödel (Speck, Spinat, Spinat-Speck, Käse, Rote Beete, Semmelknödel mit Speck &
Käse, Kaspressknödel), Fleischstrudel and the canned Gulaschsuppe (FELIX can on the packshot — brand vision-checked).
Excluded: Leberknödel (soup insert), the 6er Knödel-Mix (bundle), Rotkraut/Sauerkraut (sides), Probier-Pakete, all
sausages, cured meat, cheese, jams, condiments, sweets and drinks.
Shipping (AGB §8 + home page, read 2026-10-25): dispatched Mon/Tue only, AT 1–4 working days, DE/IT 3–7, EU ≤10;
chilled packaging; free shipping from 80 € in AT and from 100 € in Europe; shipping fee below that not published.
No nutrition, no GTIN published (never guessed).
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://schmankerl-oesterreich.at"
STORE = "Online: Schmankerl Österreich"
OPERATOR = "Pamela Plüschke – Salzburg Spezialitäten (Einzelunternehmen), Wenigaschau 1, 5143 Feldkirchen"
SHIPPING_NOTE = ("Kühlversand, Versand nur Mo/Di; AT 1–4 Werktage, DE/IT 3–7, EU max. 10; versandkostenfrei ab 80 € (AT) "
                 "bzw. 100 € (Europa); Versandkosten darunter nicht publiziert")
INCLUDE = re.compile(r"kn(?:ö|oe)del|strudel|suppe", re.I)
EXCLUDE = re.compile(r"leberkn|lebensknödel|mix|paket|probier|leberk(?:ä|ae)se|kletzen|suppeneinlagen-set", re.I)
BRAND = {"gulaschsuppe": "Felix"}          # vision-checked packshot (FELIX Gulaschsuppe can)
IMAGE_INDEX = {"speckknoedel": 1}         # image 0 duplicates the Spinat-Speck-Knödel packshot


def _text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/products.json?limit=250", timeout=40).get("products", [])


def is_meal(sp: dict) -> bool:
    h = (sp.get("handle") or "") + " " + (sp.get("title") or "")
    return bool(INCLUDE.search(h)) and not EXCLUDE.search(h)


def _field(t: str, label: str, stop=r"Zutaten|Allergene|Herkunft|Lagerung|Inhalt|Tipp") -> str | None:
    m = re.search(label + r":\s*(.*?)(?=\s+(?:" + stop + r")\s*:|$)", t)
    return m.group(1).strip(" .") or None if m else None


def parse_body(body_html: str, title: str = "") -> dict:
    t = _text(body_html)
    inhalt = _field(t, "Inhalt")
    size = None
    for s in (inhalt or "", title, t[-40:]):
        m = re.search(r"\(?(\d{2,4})\s*g\b(?!\s*gesamt)", s)
        if m and not re.search(r"je\s+\d", s):
            size = float(m.group(1)); break
    pieces = re.search(r"(\d+)\s*St(?:ü|ue)ck", inhalt or "")
    ing = _field(t, "Zutaten")
    ing = re.split(r"\.?\s*Aus Österreich\b", ing)[0].strip(" .") if ing else None
    return {"ingredients": ing, "allergens": _field(t, "Allergene"), "origin": _field(t, "Herkunft"),
            "storage": _field(t, "Lagerung"), "content": inhalt, "size_g": size,
            "pieces": int(pieces.group(1)) if pieces else None}


def to_product(sp: dict) -> Product:
    v = (sp.get("variants") or [{}])[0]
    h = sp.get("handle") or ""
    price = float(v["price"]) if v.get("price") else None
    d = parse_body(sp.get("body_html") or "", sp.get("title") or "")
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    k = IMAGE_INDEX.get(h, 0)
    size = d["size_g"]
    return Product(
        source="schmankerl", store=STORE, name=(sp.get("title") or "").strip(), brand=BRAND.get(h, "Schmankerl Österreich"),
        price_eur=price, unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None, size_g=size, nutrition_100g={}, ean=(v.get("barcode") or None),
        image_url=imgs[k] if len(imgs) > k else None, producer=OPERATOR, origin=d["origin"], category="Fertiggericht",
        source_url=f"{BASE}/products/{h}", source_id=str(sp.get("id")),
        extra={"handle": h, "available": bool(v.get("available")), "ingredients": d["ingredients"],
               "allergens": d["allergens"], "storage": d["storage"], "content": d["content"], "pieces": d["pieces"],
               "kind": "Suppe" if "suppe" in h else ("Strudel" if "strudel" in h else "Knödel"),
               "images": imgs, "price_note": "Preis inkl. MwSt. lt. Shopify-Storefront (EUR)",
               "shipping_note": SHIPPING_NOTE})


def product(handle_id_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = handle_id_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or p.get("handle") == k), None)
    return to_product(sp) if sp and is_meal(sp) else None


class Schmankerl(Adapter):
    id = "schmankerl"
    store = STORE
    homepage = BASE
    notes = ("Live: public Shopify storefront products.json (1 request) of Schmankerl Österreich (Pamela Plüschke – "
             "Salzburg Spezialitäten, Feldkirchen): chilled Innviertel Knödel, Kaspressknödel, Fleischstrudel and canned "
             "Gulaschsuppe with price, Inhalt, Zutaten, Allergene, Herkunft, Lagerung, stock and photos; chilled shipping "
             "AT/DE/IT/EU Mon/Tue, free from 80 € (AT); Leberknödel, mixes, sides excluded; no nutrition/GTIN")

    def fetch(self, category="ready-meals", limit=500):
        return [to_product(sp) for sp in store_products() if is_meal(sp)][:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if is_meal(sp):
                hay = (sp.get("title", "") + " " + sp.get("handle", "") + " " + _text(sp.get("body_html", ""))).lower()
                if all(w in hay for w in words):
                    out.append(to_product(sp))
            if len(out) >= limit:
                break
        return out
