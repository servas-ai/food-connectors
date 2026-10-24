"""Steira Markt (steiramarkt.at) — regional delicatessen in Seiersberg near Graz (operator Christian Haas,
Finkengasse 1, 8055 Seiersberg-Pirka, UID ATU67970617, EU VIES valid 2026-10-24) with a WooCommerce webshop that
ships Austria-wide. Sells heat-up jar meals ('Essen im Glas': Rindsgulasch, Paprikahendl, Hühner Curry, Pute
süß-sauer, Gulasch-/Flecksuppe, Käferbohnensuppe) and fresh hand-crimped 'Kärntner Nudeln' (Kasnudeln,
Fleischnudeln, Spinat/Steinpilz/Knoblauch/Jäger and sweet Kletzen-/Apfel-/Heidelbeernudeln; partly Amlacher).

Source (public, no login/cookies; robots.txt disallows only wc-logs/uploads, add-to-cart and /wp-admin/):
  * WooCommerce Store API ``https://www.steiramarkt.at/wp-json/wc/store/v1/products?category=<id>&per_page=100``
    for categories 491 'essen-im-glas-suppen-und-einlagen' and 154 'kaerntner-kasnudel' (2 requests) — name,
    price (minor units, EUR incl. MwSt.), stock, images, description (ingredients, nutrition only where printed).
Ready meals = jar dishes/soups and Kärntner Nudeln minus clear broths ('PUR'), Gulaschsaft, Sugo (pasta sauce),
soup inserts (Strudel, Leberknödel, Kaspressknödel), plain Bandnudeln, Brettljause catering and spice gifts.
Nutrition is parsed only where the shop prints 'Brennwert … kcal' (Käferbohnensuppe); no GTIN/SKU is published.
Shipping (page 'Zustellung', 2026-10-24): AT chilled Post parcel 19,00 € (next day), DPD parcel 10,00 €;
Graz/Graz-Umgebung personal delivery by phone appointment; DE 20,00 €.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.steiramarkt.at"
STORE = "Online: Steira Markt"
PRODUCER = "Steira Markt (Christian Haas), Finkengasse 1, 8055 Seiersberg-Pirka (UID ATU67970617) — Händler"
SHIPPING_EUR = 19.0
SHIPPING_NOTE = ("Österreich: gekühltes Post-Paket 19,00 € (Next Day), DPD-Paket 10,00 €; Graz/Graz-Umgebung persönliche "
                 "Zustellung nach Terminvereinbarung; Deutschland 20,00 € (Seite 'Zustellung', 2026-10-24)")
CATEGORY_IDS = (491, 154)
MEAL = re.compile(r"im Glas|suppe|nudel", re.I)
EXCLUDE = re.compile(r"\bPUR\b|gulaschsaft|sugo|strudel|knödel|bandnudel|brettljause|ge\(h\)würz|gutschein", re.I)
NUT = {"fat": r"Fett(?:gehalt)?:?\s*([\d,]+)\s*g", "saturated_fat": r"[Gg]esättigte Fettsäuren:?\s*([\d,]+)",
       "carbs": r"Kohlenhydrate:?\s*([\d,]+)\s*g", "sugar": r"Zucker:?\s*([\d,]+)\s*g",
       "protein": r"Eiweiß:?\s*([\d,]+)\s*g", "salt": r"Salz:?\s*([\d,]+)\s*g"}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def store_products() -> list[dict]:
    seen, out = set(), []
    for cid in CATEGORY_IDS:
        for p in get(f"{BASE}/wp-json/wc/store/v1/products?category={cid}&per_page=100", timeout=60):
            if p.get("id") not in seen:
                seen.add(p.get("id")); out.append(p)
    return out


def is_meal(sp: dict) -> bool:
    name = _html.unescape(sp.get("name") or "")
    return bool(MEAL.search(name)) and not EXCLUDE.search(name)


def size_g(name: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*kg\b", name)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    m = re.search(r"(\d+)\s*g\b", name)
    return float(m.group(1)) if m else None


def nutrition(desc: str) -> dict:
    m = re.search(r"Brennwert(.{0,300})", desc)
    if not m:
        return {}
    blk = m.group(1)
    k = re.search(r"(?:(\d+)\s*kJ\s*/\s*)?(\d+)\s*kcal", blk, re.I)
    if not k:
        return {}
    out = {"kcal": float(k.group(2))}
    for key, rx in NUT.items():
        v = re.search(rx, blk)
        if v:
            out[key] = float(v.group(1).replace(",", "."))
    return out


def line_of(name: str) -> str:
    return "Kärntner Nudeln" if re.search(r"nudel", name, re.I) else "Essen im Glas"


def maker(sp: dict) -> str | None:
    alts = " ".join((i.get("name") or "") + " " + (i.get("alt") or "") for i in (sp.get("images") or []))
    desc = _clean(sp.get("description"))
    if re.search(r"SORGER", desc):
        return "Sorger (lt. Produkttext)"
    if "Mosshammer" in alts:
        return "Mosshammer (Logo in der Produktgalerie)"
    if "Amlacher" in alts:
        return "Amlacher (Bild 'Amlacher Nudel' in der Produktgalerie)"
    return None


def to_product(sp: dict) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    name = _html.unescape(sp.get("name") or "").strip()
    desc = _clean(sp.get("description") or "")
    size = size_g(name)
    z = (re.search(r"Zutaten:\s*(.+?)(?:\s(?:Lagerhinweis|Brennwert|Allergene|Inhalt|Haltbarkeit)\b|$)", desc)
         or re.search(r"ZUTATEN & INFOS\s*(.+?)(?:\s(?:Teigsorten|Allergene|Inhalt)\b|$)", desc))
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    line = line_of(name)
    return Product(
        source="steiramarkt", store=STORE, name=name, brand=f"Steira Markt {line}",
        price_eur=price, unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if size else None, size_g=size, nutrition_100g=nutrition(desc), ean=None,
        image_url=imgs[0] if imgs else None, producer=PRODUCER, category="Fertiggericht",
        source_url=sp.get("permalink") or f"{BASE}/produkt/{sp.get('slug')}/", source_id=str(sp.get("id")),
        extra={
            "wc_id": sp.get("id"), "slug": sp.get("slug"), "line": line, "maker_hint": maker(sp),
            "categories": [c.get("slug") for c in (sp.get("categories") or [])], "in_stock": sp.get("is_in_stock"),
            "ingredients": z.group(1).strip()[:600] if z else None,
            "storage": "frisch/gekühlt, einfrierbar" if line == "Kärntner Nudeln" else "Glas (eingekocht)",
            "description": desc, "images": imgs,
            "price_note": "Preis je Packung inkl. MwSt. lt. WooCommerce Store API", "shipping_eur": SHIPPING_EUR,
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(id_slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or p.get("slug") == k), None)
    return to_product(sp) if sp else None


class SteiraMarkt(Adapter):
    id = "steiramarkt"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of Steira Markt (Seiersberg/Graz, ATU67970617): heat-up jar meals "
             "and soups plus fresh Kärntner Nudeln (Kas-, Fleisch-, Spinat-, Steinpilz-, sweet Kletzen-/Apfelnudeln) "
             "with price incl. MwSt., stock, ingredients, photos, nutrition only where printed; AT-wide shipping "
             "(chilled Post 19 €, DPD 10 €); no GTIN/SKU published; 2 requests per call")

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
