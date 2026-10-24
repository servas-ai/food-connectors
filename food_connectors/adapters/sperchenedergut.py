"""Sperchenedergut (sperchenedergut.at) — Bio-Angus farm in Aspach (Bezirk Braunau, OÖ) selling its own
heat-up jar meals (330 ml, 'Nur durch Erhitzen haltbar gemacht') online with Post-Kühlversand.

Source (public, no login/cookies; robots.txt ``User-agent: *`` disallows only wp-admin, WooCommerce
upload/log folders and ``?add-to-cart=`` URLs):
  * WooCommerce Store API ``https://sperchenedergut.at/wp-json/wc/store/v1/products?per_page=100`` — the JSON
    the shop front-end uses: name, price (minor units, EUR incl. MwSt.), stock, categories, images and the
    short description with 'Menge: 330 ml' and the portion note.
Ready meals = products in category 'Fertiggerichte' minus clear stocks (Rinderfond), sauces (Bolognese
'Sauce … mit Nudeln als Beilage') and sides/soup inserts (Leberknödel); the 'Geschenkbox' duplicates
(uncategorised copies of the same jars) and gift boxes are skipped.
No nutrition, no GTIN and no ingredient list are published → never estimated.
Shipping (sperchenedergut.at/versand-und-lieferzeiten-bio-angusrind/, read 2026-10-24): Post-Kühlversand,
delivery Tue–Fri, 9,90 € per cart, free from 150 €.
Operator (sperchenedergut.at/impressum/): Sperchenedergut Monika und Karl Mayer, Wasserdobl 16, 5251 Aspach,
UID ATU76061208 (EU VIES valid 2026-10-24, name 'Mayer Karl und Mayer Monika', same address); no
Firmenbuch entry published (farm, supervising authority BH Braunau am Inn).
Polite: one request per call.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://sperchenedergut.at"
STORE = "Online: Sperchenedergut"
PRODUCER = "Sperchenedergut Monika und Karl Mayer, Wasserdobl 16, 5251 Aspach (UID ATU76061208)"
SHIPPING_NOTE = "Post-Kühlversand (Di–Fr), 9,90 € je Warenkorb, versandkostenfrei ab 150 € lt. sperchenedergut.at/versand-und-lieferzeiten-bio-angusrind/"
EXCLUDE = re.compile(r"rinderfond|fond\b|bolognese|knödel|knoedel|gutschein|geschenkbox|t-shirt", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def is_meal(sp: dict) -> bool:
    cats = [_html.unescape(c.get("name", "")) for c in (sp.get("categories") or [])]
    if "Fertiggerichte" not in cats:
        return False
    return not EXCLUDE.search(_html.unescape(sp.get("name") or "") + " " + (sp.get("slug") or ""))


def to_product(sp: dict) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    sd = _clean(sp.get("short_description") or "")
    m = re.search(r"Menge:\s*(\d+)\s*ml", sd)
    vol = float(m.group(1)) if m else None
    por = re.search(r"\((\d+)\s*g entspricht einer Portion\)", sd)
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    name = _html.unescape(sp.get("name") or "").strip()
    return Product(
        source="sperchenedergut",
        store=STORE,
        name=name,
        brand="Sperchenedergut",
        price_eur=price,
        unit_price_eur=None,
        unit=None,
        size_g=None,
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
            "volume_ml": vol,
            "portion_g": float(por.group(1)) if por else None,
            "bio_claim": bool(re.search(r"\bBio\b", name + " " + sd)),
            "short_description": sd,
            "images": imgs,
            "price_note": "Preis je Glas inkl. MwSt. lt. WooCommerce Store API",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(id_slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or p.get("slug") == k), None)
    return to_product(sp) if sp else None


class Sperchenedergut(Adapter):
    id = "sperchenedergut"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of the Bio-Angus farm Sperchenedergut (Aspach OÖ): heat-up jar meals "
             "330 ml (Gulaschsuppe, Beuschel, Chili con Carne), price incl. MwSt., stock, jar packshots; "
             "Post-Kühlversand 9,90 €, free from 150 €; no nutrition/GTIN published; 1 request per call")

    def fetch(self, category="ready-meals", limit=500):
        return [to_product(sp) for sp in store_products() if is_meal(sp)][:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if not is_meal(sp):
                continue
            hay = (sp.get("name", "") + " " + sp.get("slug", "") + " " + _clean(sp.get("short_description", ""))).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp))
        return out[:limit]
