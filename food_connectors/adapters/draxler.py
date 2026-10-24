"""Draxler Geflügel-Wild (geflügel-draxler.at) — Styrian poultry/game butcher in Mooskirchen selling its own
'Kulinarik im Glas' heat-up jar meals (360 g, 'durch Erhitzen haltbar gemacht', gekühlt +4–6 °C) online,
delivered Austria-wide with Österreichische Post 'NEXT DAY FRESH' food delivery.

Source (public, no login/cookies; robots.txt ``User-agent: *`` disallows only WooCommerce log/transient upload
folders and ``?add-to-cart=`` URLs):
  * WooCommerce Store API ``https://www.xn--geflgel-draxler-2vb.at/wp-json/wc/store/v1/products?per_page=100``
    — name, price (minor units, EUR incl. MwSt.), stock, SKU (= Artikelnummer), categories, images and the
    description with ingredients, storage, 'Gewicht: 360g' and preparation.
  * When the API description belongs to another product (seen 2026-10-24: 'Rehragout' carried the
    'Starter Genusspaket' text), the product page's 'Beschreibung' block is read instead (1 extra request).
Ready meals = categories 'Gerichte mit Fleisch', 'Suppen', 'Vegetarische Gerichte' minus the clear broth
('Klare Suppe vom Maishendl'); category 'Sonstiges' (Starter Genusspaket bundle) and Gutscheine are skipped.
No nutrition and no GTIN are published → never estimated.
Shipping: AGB (Stand 01.06.2025) — delivery to addresses within Austria by parcel service; fees are only shown
in checkout ('im Bestellprozess gesondert ausgewiesen'), so no fee is recorded.
Operator (Impressum + AGB): Draxler Geflügel-Wild GmbH, Kainachstraße 4, 8562 Mooskirchen, FN 214255g,
UID ATU52668607 (EU VIES valid 2026-10-24, same name/address), LEI 894500FBIXCSSEWGP628 (LAPSED).
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.xn--geflgel-draxler-2vb.at"
STORE = "Online: Draxler Geflügel-Wild"
PRODUCER = "Draxler Geflügel-Wild GmbH, Kainachstraße 4, 8562 Mooskirchen (FN 214255g, UID ATU52668607)"
SHIPPING_NOTE = ("Lieferung innerhalb Österreichs per Paketdienst (Post NEXT DAY FRESH, gekühlt) lt. AGB/Startseite; "
                 "Versandkosten nur im Bestellprozess ausgewiesen")
MEAL_CATS = {"gerichte-mit-fleisch", "suppen", "vegetarische-gerichte"}
EXCLUDE = re.compile(r"klare suppe|fond\b|gutschein|genusspaket", re.I)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=60)


def is_meal(sp: dict) -> bool:
    cats = {c.get("slug") for c in (sp.get("categories") or [])}
    return bool(cats & MEAL_CATS) and not EXCLUDE.search(_html.unescape(sp.get("name") or "") + " " + (sp.get("slug") or ""))


def _desc_ok(name: str, desc: str) -> bool:
    return bool(desc) and "Genusspaket" not in desc and "Warenkorb" not in desc


def page_description(permalink: str, page_html: str | None = None) -> str:
    s = page_html if page_html is not None else get(permalink, timeout=60, raw=True).decode("utf-8", "replace")
    t = _clean(re.sub(r"(?s)<(script|style).*?</\1>", " ", s))
    m = re.search(r"Beschreibung (.*?) Ähnliche Produkte", t)
    return m.group(1).strip() if m else ""


def to_product(sp: dict, page_html: str | None = None) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    name = _html.unescape(sp.get("name") or "").strip()
    desc = _clean(sp.get("description") or "")
    desc_src = "store_api"
    if not _desc_ok(name, desc):
        desc = page_description(sp.get("permalink"), page_html); desc_src = "product_page"
    m = re.search(r"Gewicht:\s*(\d+)\s*g", desc)
    size = float(m.group(1)) if m else None
    z = re.search(r"Zutaten\s*:\s*(.*?\.)\s*(?:Das|Die|Der|Gekühlt)\b", desc)
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    cats = [c.get("slug") for c in (sp.get("categories") or [])]
    return Product(
        source="draxler", store=STORE, name=name, brand="Draxler Kulinarik im Glas",
        price_eur=price, unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if size else None, size_g=size, nutrition_100g={}, ean=None,
        image_url=imgs[0] if imgs else None, producer=PRODUCER, category="Fertiggericht",
        source_url=sp.get("permalink") or f"{BASE}/produkt/{sp.get('slug')}/", source_id=str(sp.get("id")),
        extra={
            "wc_id": sp.get("id"), "slug": sp.get("slug"), "sku": sp.get("sku"), "categories": cats,
            "in_stock": sp.get("is_in_stock"), "vegetarian": "vegetarische-gerichte" in cats,
            "vegan": bool(re.search(r"\bvegan", name + " " + desc, re.I)),
            "ingredients": z.group(1).strip() if z else None,
            "storage": "gekühlt +4 °C bis +6 °C, durch Erhitzen haltbar gemacht" if "+4" in desc else None,
            "description": desc, "description_source": desc_src, "images": imgs,
            "price_note": "Preis je Glas inkl. MwSt. lt. WooCommerce Store API", "shipping_note": SHIPPING_NOTE,
        },
    )


def product(id_slug_or_url: str, shop: list[dict] | None = None, page_html: str | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or p.get("slug") == k), None)
    return to_product(sp, page_html) if sp else None


class Draxler(Adapter):
    id = "draxler"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of Draxler Geflügel-Wild GmbH (Mooskirchen Stmk): 'Kulinarik im Glas' "
             "heat-up jar meals 360 g (Rehragout, Wild-/Maishendl-Gulasch, Curry, Chili, vegetarisch/vegan, Suppen), "
             "price incl. MwSt., SKU, stock, ingredients, photos; chilled Post NEXT DAY FRESH delivery within AT; "
             "no nutrition/GTIN published; 1 request per call (+1 per product with a broken API description)")

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
