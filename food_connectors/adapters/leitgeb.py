"""Leitgeb's Kärntnernudel (kaerntnernudel.co.at) — own webshop of Leitgeb's Nudelspezialitäten aus dem Metnitztal GmbH,
Industriestraße 18, 9360 Friesach, Kärnten (FN 62213v, LG Klagenfurt; UID ATU82506478, EU VIES valid 2026-10-25 with the
same name/address; GLEIF fulltext 0 hits → no LEI). Hand-made, pre-cooked Kärntner Nudeln and Knödel, shipped cooled
within Austria and Germany (Mon–Thu, 2–6 working days after payment; fee shown only in the cart → not published).

Sources (public, no login/cookies; robots.txt disallows only wp-admin and WooCommerce log/upload folders):
  * WooCommerce Store API ``/wp-json/wc/store/v1/products?per_page=100`` — name, price (minor units, EUR incl. 10 % MwSt.),
    stock, categories, packshot.
  * product page ``/produkt/<slug>/`` — 'Zutaten & Infos' (ingredients, Teigsorten, Allergene, 'Inhalt N Stück pro Packung
    (ca. X g pro Stück)', Haltbarkeit) and 'Nährwerte' table per 100 g.
Ready meals = savoury filled Nudeln, Nudelteller mixes and filled Knödel (pre-cooked, only heat). Excluded: sweet Nudeln
(category 'Süß': Kletzen, Apfel-Zimt, Mohn, Himbeer, Heidelbeer, Süßer Nudelteller), Schlickkrapferl (soup garnish) and
plain Semmelknödel (side). Pack weight = pieces × stated approx. piece weight ('ca.'); flagged in extra.
No GTIN on the shop. Polite: 1 s between product-page requests.
"""
from __future__ import annotations
import html as _html, re, time
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://kaerntnernudel.co.at"
STORE = "Online: Leitgeb's Kärntnernudel"
PRODUCER = "Leitgeb's Nudelspezialitäten aus dem Metnitztal GmbH, Industriestraße 18, 9360 Friesach, Kärnten (FN 62213v, UID ATU82506478)"
SHIPPING_NOTE = ("gekühlter Versand Österreich/Deutschland Mo–Do, Produktion + Versand 2–6 Werktage nach Zahlungseingang (AGB §4); "
                 "Versandkosten nur im Warenkorb angezeigt → nicht veröffentlicht")
EXCLUDE = re.compile(r"schlickkrapferl|semmelkn|gutschein", re.I)
NUT = [("kcal", None), ("fat", None), ("saturated_fat", None), ("carbs", None), ("sugar", None), ("protein", None), ("salt", None)]


def _clean(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).replace("\xa0", " ").replace("\u00ad", "").strip()


def _name(sp: dict) -> str:
    return _html.unescape(sp.get("name") or "").replace("\u00ad", "").replace("&shy;", "").strip()


def _slug(sp: dict) -> str:
    return (sp.get("permalink") or "").rstrip("/").split("/")[-1]


def store_products() -> list[dict]:
    return get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100", timeout=40)


def page(sp: dict) -> str:
    return get(sp["permalink"], raw=True, headers={"Accept": "text/html"}, timeout=40).decode("utf-8", "replace")


def is_meal(sp: dict) -> bool:
    cats = {c.get("name") for c in sp.get("categories") or []}
    return "Süß" not in cats and not EXCLUDE.search(_name(sp) + " " + _slug(sp))


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def parse_page(h: str) -> dict:
    t = _clean(h)
    sec = t.split("Zutaten & Infos Zutaten & Infos", 1)[1] if "Zutaten & Infos Zutaten & Infos" in t else ""
    z = re.search(r"^(.*?)\s+(?:Teigsorten|Allergene|Inhalt)\b", sec)
    a = re.search(r"Allergene (.*?) (?:Inhalt|Haltbarkeit|Zubereitung)\b", sec)
    inh = re.search(r"Inhalt (\d+) Stück pro Packung(?: \(ca\. ?(\d+) ?g pro Stück\))?", sec)
    hb = re.search(r"Haltbarkeit (.*?) Zubereitung", sec)
    nut = {}
    n = re.search(r"Angabe pro 100 ?g ([\d.,]+) ?kJ ?/ ?([\d.,]+) ?kcal ((?:[<\d.,]+ ?g ?){6})", t)
    if n:
        vals = re.findall(r"<?([\d.,]+) ?g", n.group(3))
        nut = {"kj": _num(n.group(1)), "kcal": _num(n.group(2))}
        nut.update({k: _num(v) for (k, _), v in zip(NUT[1:], vals)})
    pieces = int(inh.group(1)) if inh else None
    piece_g = int(inh.group(2)) if inh and inh.group(2) else None
    return {"ingredients": z.group(1).strip() if z and z.group(1).strip() else None,
            "allergens": a.group(1).strip() if a else None,
            "pieces": pieces, "piece_g": piece_g,
            "size_g": float(pieces * piece_g) if pieces and piece_g else None,
            "shelf_life": hb.group(1).strip() if hb else None, "nutrition_100g": nut}


def to_product(sp: dict, h: str | None = None) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    d = parse_page(h if h is not None else page(sp))
    size = d["size_g"]
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    return Product(
        source="leitgeb", store=STORE, name=_name(sp), brand="Leitgeb's Nudelspezialitäten",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None, size_g=size,
        nutrition_100g=d["nutrition_100g"], ean=None,
        image_url=imgs[0] if imgs else None, producer=PRODUCER, category="Fertiggericht",
        source_url=sp.get("permalink") or f"{BASE}/produkt/{_slug(sp)}/", source_id=str(sp.get("id")),
        extra={"wc_id": sp.get("id"), "slug": _slug(sp), "in_stock": sp.get("is_in_stock"),
               "categories": [c.get("name") for c in sp.get("categories") or []],
               "ingredients": d["ingredients"], "allergens": d["allergens"], "pieces": d["pieces"],
               "piece_g_approx": d["piece_g"], "size_note": "Packungsgewicht = Stück × ca.-Stückgewicht lt. Shop" if size else None,
               "shelf_life": d["shelf_life"], "images": imgs,
               "price_note": "Preis je Packung inkl. 10 % MwSt. lt. WooCommerce Store API, zzgl. Versand",
               "shipping_note": SHIPPING_NOTE})


def product(id_slug_or_url: str, shop: list[dict] | None = None, html: str | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or _slug(p) == k), None)
    return to_product(sp, html) if sp and is_meal(sp) else None


class Leitgeb(Adapter):
    id = "leitgeb"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API + product pages of Leitgeb's Kärntnernudel (Friesach, Kärnten; FN 62213v): "
             "hand-made pre-cooked Kärntner Nudeln, Nudelteller and filled Knödel with price incl. MwSt., stock, ingredients, "
             "allergens, pieces/approx. weight, nutrition per 100 g, packshot; sweet Nudeln, Schlickkrapferl and Semmelknödel "
             "excluded; cooled shipping AT/DE (fee only in cart); no GTIN; 1 + N requests at 1 s")

    def fetch(self, category="ready-meals", limit=500):
        out = []
        for sp in store_products():
            if is_meal(sp) and len(out) < limit:
                out.append(to_product(sp)); time.sleep(1)
        return out

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            hay = (_name(sp) + " " + _slug(sp) + " " + _clean(sp.get("short_description", "")) + " " + _clean(sp.get("description", ""))).lower()
            if is_meal(sp) and all(w in hay for w in words) and len(out) < limit:
                out.append(to_product(sp)); time.sleep(1)
        return out
