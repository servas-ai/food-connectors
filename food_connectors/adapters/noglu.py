"""noglu — NoGlu glutenfreie Knödel-Manufaktur (noglu.at, WooCommerce + Germanized): gluten- and lactose-free,
fully cooked, vacuum-packed frozen Tyrolean Knödel/Nocken. Operator per Impressum/VIES: Andreas Rossmeier,
Einzelunternehmen, Ziegelweg 10, 6060 Hall in Tirol, Tirol (no Firmenbuch entry; GISA 35944898; UID ATU62240088 —
EU VIES valid 2026-10-25, name 'Rossmeier Andreas Markus', address 'Ziegelweg 10, AT-6060 Hall in Tirol';
GLEIF: no LEI). Also runs Andis Grillwelt / MONOLITH Keramikgrills.

Source (public, no login/cookies; robots.txt disallows only wp-admin, cart/checkout/account and WC logs/uploads):
  * WooCommerce Store API ``/wp-json/wc/store/v1/products?per_page=100`` (one request) — name, SKU, price (minor
    units, EUR incl. MwSt.), stock, weight, packshot, description with 'Inhalt: 4 Stück à 125 g' and the
    'Nährwerte' table (per 100 g; note on the shop: values refer to the recipe before cooking).
Ready meals = Kaspressknödel, Speckknödel, Spinatknödel, Kasnocken. Semmelknödel (plain side dish) and the
mixed boxes (Probiersortiment / Familienbox / Vorratsbox = bundles of the same packs) are excluded.
No ingredients list and no GTIN published → empty, never estimated.
Shipping (Versand & Lieferung): AT and DE, frozen in thermo cartons, dispatched Wednesdays (orders by Tue 12:00);
AT 16,90 € / DE 25,90 € per carton of up to 28 packs (14 kg).
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.noglu.at"
STORE = "Online: NoGlu (glutenfreie Knödel)"
BRAND = "NoGlu"
PRODUCER = "Andreas Rossmeier (Einzelunternehmen), Ziegelweg 10, 6060 Hall in Tirol, Tirol (UID ATU62240088, GISA 35944898)"
SHIPPING_NOTE = ("tiefgekühlt im Thermokarton, Versand mittwochs (Bestellung bis Di 12 Uhr); "
                 "AT 16,90 € / DE 25,90 € je Karton bis 28 Packungen (14 kg)")
SHIPPING_AT = 16.9
EXCLUDE = re.compile(r"semmelkn|box|sortiment", re.I)
_N = r"(\d+(?:,\d+)?)"
NUT = [("fat", r"^Fett\s+" + _N + r"\s*g"), ("satfat", r"gesättigte Fettsäuren\s+" + _N + r"\s*g"),
       ("carbs", r"Kohlenhydrate\s+" + _N + r"\s*g"), ("sugar", r"davon Zucker\s+" + _N + r"\s*g"),
       ("fiber", r"Ballaststoffe\s+" + _N + r"\s*g"), ("protein", r"Eiweiß\s+" + _N + r"\s*g"),
       ("salt", r"Salz\s+" + _N + r"\s*g")]


def _f(s):
    return float(s.replace(",", ".")) if s else None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def _name(sp: dict) -> str:
    return _html.unescape(sp.get("name") or "").strip()


def _slug(sp: dict) -> str:
    return sp.get("slug") or (sp.get("permalink") or "").rstrip("/").split("/")[-1]


def _price(sp: dict):
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    return int(pr["price"]) / 10 ** mu if pr.get("price") else None


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def is_meal(sp: dict) -> bool:
    return bool(sp) and not EXCLUDE.search(_name(sp) + " " + _slug(sp) + " " + (sp.get("sku") or ""))


def nutrition(desc_html: str) -> tuple[dict, float | None]:
    """Per-100-g column of the 'Nährwerte' table (first value cell of each row)."""
    rows = re.findall(r"<tr[^>]*>\s*<th>(.*?)</th>\s*<td>(.*?)</td>", desc_html or "", re.S)
    out, kj = {}, None
    for th, td in rows:
        line = f"{_clean(th)} {_clean(td)}"
        e = re.match(r"Brennwert\s+" + _N + r"\s*kJ\s*/\s*" + _N + r"\s*kcal", line)
        if e:
            kj, out["kcal"] = _f(e.group(1)), _f(e.group(2))
            continue
        for k, rx in NUT:
            m = re.search(rx, line)
            if m and k not in out:
                out[k] = _f(m.group(1))
    return out, kj


def to_product(sp: dict) -> Product:
    txt = _clean(sp.get("description"))
    m = re.search(r"Inhalt:\s*(\d+)\s*Stück\s*à\s*(\d+)\s*g", txt)
    pieces, piece_g = (int(m.group(1)), float(m.group(2))) if m else (None, None)
    size = pieces * piece_g if m else (float(sp["weight"]) * 1000 if sp.get("weight") else None)
    price = _price(sp)
    nut, kj = nutrition(sp.get("description"))
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    return Product(
        source="noglu", store=STORE, name=_name(sp), brand=BRAND, price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None, size_g=size, nutrition_100g=nut, ean=None,
        image_url=imgs[0] if imgs else None, producer=PRODUCER, origin="AT (Tirol, Hall in Tirol, eigene Manufaktur)",
        category="Fertiggericht", source_url=sp.get("permalink") or f"{BASE}/product/{_slug(sp)}/",
        source_id=sp.get("sku") or str(sp.get("id")),
        extra={"wc_id": sp.get("id"), "slug": _slug(sp), "sku": sp.get("sku"), "in_stock": sp.get("is_in_stock"),
               "pieces": pieces, "piece_g": piece_g, "kj_100": kj,
               "nutrition_note": "Werte pro 100 g lt. Shop bezogen auf die Rezeptur vor dem Kochen",
               "short_description": _clean(sp.get("short_description")),
               "glutenfrei": True, "laktosefrei": True, "frozen": True, "packaging": "vakuumverpackt",
               "prep": "fertig gegart, tiefgekühlt; erhitzen lt. Shop (Zubereitung)",
               "price_note": "inkl. MwSt., zzgl. Versandkosten lt. Produktseite", "shipping_note": SHIPPING_NOTE})


def all_products(shop: list[dict] | None = None) -> list[Product]:
    return [to_product(sp) for sp in (shop if shop is not None else store_products()) if is_meal(sp) and _price(sp)]


def product(id_slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    for sp in (shop if shop is not None else store_products()):
        if k in (str(sp.get("id")), _slug(sp), sp.get("sku")):
            return to_product(sp) if is_meal(sp) else None
    return None


class NoGlu(Adapter):
    id = "noglu"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of noglu.at (NoGlu, Einzelunternehmen Andreas Rossmeier, "
             "Hall in Tirol; UID ATU62240088): gluten- and lactose-free frozen Kaspressknödel, Speckknödel, Spinatknödel, "
             "Kasnocken 4×125 g at 9,00 € incl. MwSt. with nutrition per 100 g; Semmelknödel (side) and boxes excluded; "
             "no ingredients/GTIN; frozen shipping AT 16,90 € per carton (≤28 packs), Wednesdays")

    def fetch(self, category="ready-meals", limit=500):
        return all_products()[:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            hay = (_name(sp) + " " + _slug(sp) + " " + _clean(sp.get("description"))).lower()
            if is_meal(sp) and _price(sp) and all(w in hay for w in words):
                out.append(to_product(sp))
            if len(out) >= limit:
                break
        return out
