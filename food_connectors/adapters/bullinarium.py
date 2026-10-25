"""Bullinarium online shop (bullinarium.com) — direct-marketing shop of Hallers Bull Beef® from Markt Allhau, Bezirk
Oberwart, Burgenland ('Österreichs größte Kreislauflandwirtschaft'). Operator per shop AGB: Haller GmbH, Gemeindestraße 30,
7411 Markt Allhau (FN 492415s, Landesgericht Eisenstadt; UID ATU73356147 — EU VIES valid 2026-10-25 with the same
name/address; GLEIF: no LEI).

Source (public, no login/cookies; TYPO3 robots.txt disallows only /typo3*/, /t3lib/, /tslib/, /fileadmin/template/ and the
shop checkout paths /de/online-shop/kassa/ + /order-handling/):
  * category page ``/de/online-shop/c/fix-fertig/`` ('Fix & Fertig — Bullinarium-Küche für Daheim') → product links;
  * each product page's schema.org ``Product`` JSON-LD (name, packshot, description with 'Zutaten', sku = Art.Nr.,
    offer price EUR incl. 10 % USt., availability) + the visible ``shopPricePerUnit`` line ('0,35 kg (€ 33,60 pro
    Kilogramm)' / '0,35 l' / '2,80 kg').
1 + n requests, 1 s apart. Ready meals = Fix & Fertig minus sauces/condiments (Sugo, BBQ Sauce, Chili Mayo, Essence) and the
'Fix & Fertig Duo' bundle (= Gulasch + Chili jars, would duplicate). Geschmorte Wade (2,8 kg, 4–6 persons) and BBQ Ribs
(1,2 kg) are fully cooked and only need re-heating/finishing in the oven; both 'auf Anfrage lieferbar / derzeit ausverkauft'.
No nutrition and no GTIN are published → never estimated. Shipping (Liefer- & Versandbedingungen + AGB §4): Post parcel
within Austria Tue–Fri 14,90 € per order, free from 120 €; pick-up in Markt Allhau by phone.
"""
from __future__ import annotations
import html as _html, json, re, time
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.bullinarium.com"
CATEGORY_URL = f"{BASE}/de/online-shop/c/fix-fertig/"
STORE = "Online: Bullinarium (Hallers Bull Beef)"
BRAND = "Hallers Bull Beef"
PRODUCER = "Haller GmbH (Bullinarium), Gemeindestraße 30, 7411 Markt Allhau, Burgenland (FN 492415s, UID ATU73356147)"
SHIPPING_EUR = 14.90
SHIPPING_NOTE = "Post-Paket Österreich (Zustellung Di–Fr) 14,90 € pro Bestellung, ab 120 € versandkostenfrei; Abholung Markt Allhau nach tel. Vereinbarung"
EXCLUDE = re.compile(r"sugo|sauce|mayo|essence|duo|gutschein|k(ü|ue)hl", re.I)
LD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
UNIT = re.compile(r'class="shopPricePerUnit">\s*([\d.,]+)\s*(kg|g|l|ml)\b')


def _get_html(url: str) -> str:
    return get(url, raw=True, headers={"Accept": "text/html"}, timeout=40).decode("utf-8", "replace")


def _clean(s: str) -> str:
    s = _html.unescape(_html.unescape(s or ""))
    s = re.sub(r"<br\s*/?>|</p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s).replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in s.splitlines() if l.strip())


def product_slugs(page: str | None = None) -> list[str]:
    page = page if page is not None else _get_html(CATEGORY_URL)
    out = []
    for s in re.findall(r'href="[^"]*/online-shop/produkt/c/fix-fertig/p/([^/"]+)/?"', page):
        if s not in out:
            out.append(s)
    return out


def is_meal(slug_or_name: str) -> bool:
    return not EXCLUDE.search(slug_or_name or "")


def ld_product(page: str) -> dict | None:
    for m in LD.findall(page):
        try:
            d = json.loads(m)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            return d
    return None


def parse_size(page: str) -> tuple[float | None, str | None]:
    m = UNIT.search(page)
    if not m:
        return None, None
    v = float(m.group(1).replace(".", "").replace(",", "."))
    u = m.group(2)
    g = v * 1000 if u in ("kg", "l") else v
    return round(g, 1), f"{m.group(1)} {u}"


def parse_ingredients(desc: str) -> str | None:
    m = re.search(r"Zutaten(?: Chili| Gulasch)?\s*:\s*(.+?)(?:\n|$)", desc, re.I)
    return m.group(1).strip().rstrip(".") if m else None


def parse(page: str, slug: str) -> Product | None:
    d = ld_product(page)
    if not d or not is_meal(slug) or not is_meal(d.get("name") or ""):
        return None
    off = d.get("offers") or {}
    price = float(off["price"]) if off.get("price") else None
    size, size_label = parse_size(page)
    desc = _clean(d.get("description") or "")
    img = d.get("image")
    img = img[0] if isinstance(img, list) else img
    pers = re.search(r"ausreichend für\s*(\d+)\s*bis\s*(\d+)\s*Personen", desc)
    return Product(
        source="bullinarium", store=STORE, name=re.sub(r"\s+", " ", _html.unescape(d.get("name") or "")).strip(), brand=BRAND,
        price_eur=price, unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None, size_g=size, nutrition_100g={}, ean=None, image_url=img or None,
        producer=PRODUCER, category="Fertiggericht",
        source_url=off.get("url") or f"{BASE}/online-shop/produkt/c/fix-fertig/p/{slug}/", source_id=str(d.get("sku") or slug),
        extra={"slug": slug, "sku": d.get("sku"), "in_stock": (off.get("availability") or "").endswith("InStock"),
               "size_label": size_label, "ingredients": parse_ingredients(desc),
               "persons": f"{pers.group(1)}–{pers.group(2)}" if pers else None,
               "on_request": "auf Anfrage lieferbar" in page, "description": desc[:600],
               "price_note": "Preis inkl. 10 % USt. lt. Produktseite (schema.org Offer), zzgl. Versand",
               "shipping_eur": SHIPPING_EUR, "shipping_note": SHIPPING_NOTE})


def product(slug_or_url: str, page_html: str | None = None) -> Product | None:
    slug = slug_or_url.strip().rstrip("/").split("/")[-1]
    if not is_meal(slug):
        return None
    if page_html is None:
        try:
            page_html = _get_html(f"{BASE}/online-shop/produkt/c/fix-fertig/p/{slug}/")
        except Exception:
            return None
    return parse(page_html, slug)


def all_products(pages: dict[str, str] | None = None, category_page: str | None = None) -> list[Product]:
    out = []
    for i, s in enumerate(product_slugs(category_page)):
        if not is_meal(s):
            continue
        if pages is None and i:
            time.sleep(1)
        p = product(s, pages.get(s) if pages is not None else None)
        if p:
            out.append(p)
    return out


class Bullinarium(Adapter):
    id = "bullinarium"
    store = STORE
    homepage = BASE
    notes = ("Live: Bullinarium online shop (Haller GmbH, Markt Allhau, Burgenland; FN 492415s, UID ATU73356147) — "
             "'Fix & Fertig' category + product-page schema.org JSON-LD: Hallers Bull Beef Gulasch 350 g and Chili con Bull "
             "Beef 0,35 l (11,76 € each, ingredients), geschmorte Wade 2,8 kg (64,90 €) and BBQ Ribs 1,2 kg (32,90 €, both on "
             "request); Sugo/sauces/mayo/essence and the Duo bundle excluded; no nutrition/GTIN; Post AT 14,90 €, free "
             "from 120 €; 1 + n requests, 1 s apart")

    def fetch(self, category="ready-meals", limit=50):
        return all_products()[:limit]

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = [p for p in all_products()
               if all(w in f"{p.name} {p.extra.get('slug')} {p.extra.get('ingredients') or ''}".lower() for w in words)]
        return out[:limit]
