"""Lomo Alto (lomoalto.at) — LOMO ALTO OG, Atzgersdorf 4, 4141 Pfarrkirchen im Mühlkreis (OÖ), Bio beef farm
('Mühlviertler Bio-Rind', older cattle) selling its own heat-up Bio jar meals ('Fertigprodukte im Glas', 400 g) in a
Shopify webshop, delivered only within Austria.

Source (public Shopify storefront, no login/cookies; robots.txt ``User-agent: *`` ``Allow: /``):
  * ``https://lomoalto.at/products.json?limit=250`` — the storefront JSON: title, SKU, price (EUR incl. MwSt.),
    availability, description, tags, product images. One request.
Ready meals = SKU FERTIGP* with tag 'Fertigprodukte im Glas' and 'im Glas 400g' in the title, minus broth
(Knochensuppe), Sulz, Nierenfett and Leberpasteten → Rindergulasch, Rotweinragout, Chili con Carne.
Label data: the shop publishes each jar's printed label as a product image (``lomoalto_etikett_<dish>_v4_...jpg``,
500 px). Ingredients, 'Nährwerte pro 100 g' (energy in kJ only, fat, saturates, carbs, sugar, protein, salt) and the
EAN-13 below the barcode were transcribed by hand from those labels on 2026-10-24 (all three EAN check digits valid)
and are applied only while the live feed still carries the same label image URL (else left empty, never guessed).
kcal = label kJ / 4.184 (unit conversion, not an estimate; Atwater-consistent). Label producer: 'Stressfrei Biofleisch
GesbR, Atzgersdorf 4, 4141 Pfarrkirchen' (same address as the shop operator), AT-BIO-402, 'gekühlt lagern (6–9 °C)'.
Shipping (policies/shipping-policy + AGB §5/§6, read 2026-10-24): only within Austria, up to 14 working days, shelf
products in normal cardboard boxes (store the jars chilled again on arrival); fee depends on quantity/method and is
shown only in the checkout → shipping_eur empty.
Operator (policies/legal-notice): LOMO ALTO OG, owners Martin Sageder & Josef Wiesinger, UID ATU77712619 (VIES valid
2026-10-24: 'Lomo Alto OG', Atzgersdorf 4, AT-4141 Pfarrkirchen/Mühlkreis); no FN published, no GLEIF record.
Photos: first product image = jar packshot with printed dish name; vision gate 2026-10-24 3/3 PASS.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://lomoalto.at"
STORE = "Online: Lomo Alto"
PRODUCER = "LOMO ALTO OG, Atzgersdorf 4, 4141 Pfarrkirchen (UID ATU77712619); Etikett: Stressfrei Biofleisch GesbR, gleiche Adresse"
SHIPPING_EUR = None
SHIPPING_NOTE = ("Lieferung nur innerhalb Österreichs (AGB §6, bis 14 Werktage); Glasprodukte im Versandkarton, "
                 "nach Erhalt wieder gekühlt lagern; Versandkosten mengen-/versandartabhängig, erst im Bestellvorgang (AGB §5)")
STORAGE = "Glas, nur durch Erhitzen haltbar gemacht, ohne Konservierungsstoffe; gekühlt lagern (6–9 °C) lt. Etikett"
SHELF_LIFE = "ca. 8 Wochen lt. Shop"
EXCLUDE = re.compile(r"knochensuppe|sulz|nierenfett|leberpastete", re.I)
# transcribed from the shop's own label images 2026-10-24 (see module docstring); key = Shopify SKU
LABEL = {
    "FERTIGP1": {"label": "lomoalto_etikett_gulasch_v4_endversion_1.jpg", "ean": "9120082120050",
                 "ingredients": "Rindfleisch*, Zwiebel*, Sonnenblumenöl*, Paprikapulver*, Steinsalz, Pfeffer*, Lorbeerblätter* (*aus kontrolliert biologischer Landwirtschaft)",
                 "kj": 617.57, "fat": 9.00, "satfat": 3.93, "carbs": 2.84, "sugar": 2.51, "protein": 13.85, "salt": 0.63},
    "FERTIGP2": {"label": "lomoalto_etikett_rotweinragout_v4_endversion_1.jpg", "ean": "9120082120111",
                 "ingredients": "Rindfleisch*, Zwiebel*, Tomaten*, 9% Rotwein*, Karotten*, SELLERIE*, Sonnenblumenöl*, Petersilie*, Steinsalz, Maisstärke*, Pfeffer* (*aus kontrolliert biologischer Landwirtschaft)",
                 "kj": 659.10, "fat": 9.44, "satfat": 4.16, "carbs": 2.13, "sugar": 1.78, "protein": 14.40, "salt": 0.62},
    "FERTIGP4": {"label": "lomoalto_etikett_chiliconcarne_v4_endversion_1.jpg", "ean": "9120082120067",
                 "ingredients": "Tomaten*, Rindfleisch*, Zwiebel*, Karotten*, Kidneybohnen*, Zuckermais*, Sonnenblumenöl*, Steinsalz, Paprikapulver*, Pfeffer*, Chilipulver* (*aus kontrolliert biologischer Landwirtschaft)",
                 "kj": 362.15, "fat": 4.34, "satfat": 1.84, "carbs": 4.09, "sugar": 2.56, "protein": 7.29, "salt": 0.59},
}


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/products.json?limit=250", timeout=40).get("products", [])


def _sku(sp: dict) -> str:
    return ((sp.get("variants") or [{}])[0].get("sku") or "")


def is_meal(sp: dict) -> bool:
    t = sp.get("title") or ""
    return (_sku(sp).startswith("FERTIGP") and "Fertigprodukte im Glas" in (sp.get("tags") or [])
            and re.search(r"im Glas\s*\d+\s*g", t) is not None and not EXCLUDE.search(t + " " + (sp.get("handle") or "")))


def _label(sp: dict) -> dict | None:
    lab = LABEL.get(_sku(sp))
    if lab and any(lab["label"] in (i.get("src") or "") for i in (sp.get("images") or [])):
        return lab
    return None


def to_product(sp: dict) -> Product:
    v = (sp.get("variants") or [{}])[0]
    price = float(v["price"]) if v.get("price") else None
    m = re.search(r"(\d+)\s*g\b", sp.get("title") or "")
    size = float(m.group(1)) if m else None
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    photo = next((u for u in imgs if "etikett" not in u), None)
    lab = _label(sp)
    nut = {}
    if lab:
        nut = {"kcal": round(lab["kj"] / 4.184, 1), "kj": lab["kj"]}
        nut.update({k: lab[k] for k in ("fat", "satfat", "carbs", "sugar", "protein", "salt")})
    return Product(
        source="lomoalto",
        store=STORE,
        name=(sp.get("title") or "").strip(),
        brand="LOMO ALTO",
        price_eur=price,
        unit_price_eur=round(price / size * 100, 2) if price and size else None,
        unit="100 g" if price and size else None,
        size_g=size,
        nutrition_100g=nut,
        ean=lab["ean"] if lab else (v.get("barcode") or None),
        image_url=photo,
        producer=PRODUCER,
        origin="AT (Mühlviertler Bio-Rind, eigener Betrieb Pfarrkirchen OÖ lt. Shop/Etikett)",
        category="Fertiggericht",
        source_url=f"{BASE}/products/{sp.get('handle')}",
        source_id=str(sp.get("id")),
        extra={
            "handle": sp.get("handle"),
            "sku": v.get("sku"),
            "available": bool(v.get("available")),
            "bio_claim": True,
            "bio_control": "AT-BIO-402 lt. Etikett",
            "description": _text(sp.get("body_html")),
            "ingredients": lab["ingredients"] if lab else None,
            "label_image": next((u for u in imgs if "etikett" in u), None),
            "nutrition_source": "Etikett-Bild im Shop (von Hand transkribiert 2026-10-24); kcal = kJ/4,184" if lab else None,
            "storage": STORAGE,
            "shelf_life": SHELF_LIFE,
            "price_note": "Preis je Glas inkl. MwSt. lt. Shopify-Storefront (EUR)",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(handle_id_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = handle_id_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    sp = next((p for p in (shop if shop is not None else store_products())
               if str(p.get("id")) == k or p.get("handle") == k or _sku(p) == k), None)
    return to_product(sp) if sp else None


class LomoAlto(Adapter):
    id = "lomoalto"
    store = STORE
    homepage = BASE
    notes = ("Live: public Shopify storefront of LOMO ALTO OG (Pfarrkirchen OÖ): 3 Bio heat-up jar meals 400 g "
             "(Rindergulasch, Rotweinragout, Chili con Carne) with price, availability, packshot; ingredients, nutrition "
             "and EAN transcribed from the shop's label images; AT-only delivery, fee in checkout; 1 request")

    def fetch(self, category="ready-meals", limit=500):
        return [to_product(sp) for sp in store_products() if is_meal(sp)][:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if not is_meal(sp):
                continue
            hay = (sp.get("title", "") + " " + _text(sp.get("body_html"))).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp))
        return out[:limit]
