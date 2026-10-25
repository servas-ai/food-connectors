"""Wiesbauer Gourmet own webshop (wiesbauer-gourmet.at) — Wiesbauer Gourmet Gastro GmbH, Reidling NÖ, sells its
'Easy Kitchen' heat-up dishes (Rindergulasch, Hirschgulasch, Kalbsrahmbeuschel, Rinderbacken, Putengeschnetzeltes)
and its 'Sous Vide' line of fully pre-cooked mains (Ente/Gans halbiert, Stelzen, Spareribs, Tafelspitz, Lammstelze,
Shortribs, Knusperbraten) online, shipped chilled in a cool box to Austria and Germany.

Source (public, no login/cookies; robots.txt disallows only /wp-admin/):
  * WooCommerce Store API ``https://www.wiesbauer-gourmet.at/wp-json/wc/store/v1/products?category=<id>&per_page=100``
    for categories 3138 'easy-kitchen', 154 'sous-vide', 3137 'wirtshauskultur-fuer-daheim' (3 requests) — name,
    price (minor units, EUR incl. MwSt.), stock, SKU, images and the description with 'Nährwerte pro 100 g',
    'Zutaten' and preparation.
Ready meals = items in those categories that are pre-cooked ('sous vide vorgegart', 'Easy Kitchen', 'servierfertig',
'gegart') minus sauces/jus/fond, side dishes (Knödel, Rotkraut), bundles ('Paket'/'Package'), raw meat, Beef Tatar,
Würstel, breaded frozen raw schnitzel/cordon bleu, Pulled Pork (burger filling) and the 2 kg Roastbeef joint.
Nutrition is parsed only where the shop prints it per 100 g. GTIN: the Store API carries none (SKU only), but each
product page embeds a schema.org Product JSON-LD with ``gtin`` (19/20 meals, 2026-10-25T1339; Hirschgulasch has none)
→ read via ``page_gtin`` (1 extra request per product, opt-in ``with_gtin=True``), GS1 check digit validated; codes
are never derived from the SKU.
Shipping (Versand page + AGB §5, 2026-10-24): AT and DE only; € 19,90 flat up to € 149, free from € 150;
24 h delivery Tue–Sat with cool box/ice packs.
Operator (Impressum): Wiesbauer Gourmet Gastro GmbH, Wiesbauer Straße 1, 3454 Reidling, FN 98447a,
UID ATU20162703 (EU VIES valid 2026-10-24, same name/address).
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.wiesbauer-gourmet.at"
STORE = "Online: Wiesbauer Gourmet"
PRODUCER = "Wiesbauer Gourmet Gastro GmbH, Wiesbauer Straße 1, 3454 Reidling (FN 98447a, UID ATU20162703)"
SHIPPING_EUR = 19.9
SHIPPING_NOTE = ("Lieferung nur AT/DE gekühlt in Wiesbauer-Gourmet-Box; Versandpauschale 19,90 € bis 149 € Bestellwert, "
                 "ab 150 € versandkostenfrei (Versand-Seite + AGB §5, 2026-10-24)")
CATEGORY_IDS = (3138, 154, 3137)
COOKED = re.compile(r"sous.?vide|vorgegart|servierfertig|easy kitchen|gegart", re.I)
EXCLUDE = re.compile(r"saft\b|sauce|fond\b|jus\b|tatar|knödel|rotkraut|paket|package|gutschein|würstel|speck|"
                     r"markknochen|paniert|cordon|pulled pork|roastbeef|duroc|iberico|filet|steak|scherzl|schinken", re.I)
NUT = {"fat": r"Fett:?\s*<?\s*([\d,]+)\s*g", "saturated_fat": r"ges(?:ättigte|\.)\s*(?:Fettsäuren|FS\.?):?\s*<?\s*([\d,]+)",
       "carbs": r"Kohlenhydrate:?\s*<?\s*([\d,]+)\s*g", "sugar": r"Zucker:?\s*<?\s*([\d,]+)\s*g",
       "protein": r"Eiweiß:?\s*<?\s*([\d,]+)\s*g", "salt": r"Salz:?\s*<?\s*([\d,]+)"}


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
    return bool(COOKED.search(name + " " + _clean(sp.get("description")))) and not EXCLUDE.search(name)


def size_g(name: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*kg\b", name)
    if m:
        return float(m.group(1).replace(",", ".")) * 1000
    m = re.search(r"(\d{1,2}\.\d{3}|\d+)\s*g\b", name)
    return float(m.group(1).replace(".", "")) if m else None


def nutrition(desc: str) -> dict:
    m = re.search(r"Nährwerte pro 100\s*(?:g|Gramm)(.{0,400})", desc)
    if not m:
        return {}
    blk = m.group(1)
    out = {}
    k = re.search(r"(?:(\d+)\s*kj\s*/\s*)?(\d+)\s*kcal", blk, re.I)
    if not k:
        return {}
    if k.group(1) and abs(float(k.group(1)) / 4.184 - float(k.group(2))) > 0.15 * float(k.group(2)):
        return {}  # shop prints kJ and kcal that contradict each other (e.g. Tafelspitz 375 kJ/388 kcal) -> not used
    out["kcal"] = float(k.group(2))
    for key, rx in NUT.items():
        v = re.search(rx, blk)
        if v:
            out[key] = float(v.group(1).replace(",", "."))
    return out if "kcal" in out else {}


def nut_flag(desc: str) -> str | None:
    if re.search(r"Nährwerte pro 100", desc) and not nutrition(desc):
        return "shop_kj_kcal_inconsistent"
    if re.search(r"Nährwerte pro 100.{0,300}<\s*0,5", desc):
        return "lt_0.5_recorded_as_0.5"
    return None


def _gs1_ok(c: str) -> bool:
    if not c.isdigit() or len(c) not in (8, 12, 13, 14):
        return False
    d = [int(x) for x in c]
    return (10 - sum(v * (3 if i % 2 == 0 else 1) for i, v in enumerate(reversed(d[:-1]))) % 10) % 10 == d[-1]


def jsonld_gtin(page: str) -> str | None:
    """GS1-valid gtin/gtin13 from the schema.org Product JSON-LD of a product page (None if absent/invalid)."""
    import json as _json
    for blk in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page or "", re.S):
        try:
            stack = [_json.loads(blk)]
        except ValueError:
            continue
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                if o.get("@type") == "Product":
                    for k in ("gtin13", "gtin", "gtin14", "gtin12", "gtin8"):
                        c = str(o.get(k) or "").strip()
                        if c and _gs1_ok(c):
                            return c
                stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
    return None


def page_gtin(url: str) -> str | None:
    try:
        return jsonld_gtin(get(url, timeout=40, raw=True).decode("utf-8", "replace"))
    except Exception:
        return None


def to_product(sp: dict, gtin: str | None = None) -> Product:
    pr = sp.get("prices") or {}
    mu = int(pr.get("currency_minor_unit") or 2)
    price = int(pr["price"]) / 10 ** mu if pr.get("price") else None
    name = _html.unescape(sp.get("name") or "").strip()
    desc = _clean(sp.get("description") or "")
    size = size_g(name) or size_g(desc[:120])
    z = re.search(r"Zutaten:?\s*(?:Gluten- und Laktosefrei!\s*)?(?:Zutaten:?\s*)?([A-ZÄÖÜ1-9].*?\.)\s", desc)
    imgs = [i["src"] for i in (sp.get("images") or []) if i.get("src")]
    cats = [c.get("slug") for c in (sp.get("categories") or [])]
    line = "Easy Kitchen" if ("easy-kitchen" in cats or "Easy Kitchen" in name + desc) else "Sous Vide"
    return Product(
        source="wiesbauer_gourmet", store=STORE, name=name, brand=f"Wiesbauer Gourmet {line}",
        price_eur=price, unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if size else None, size_g=size, nutrition_100g=nutrition(desc), ean=gtin,
        image_url=imgs[0] if imgs else None, producer=PRODUCER, category="Fertiggericht",
        source_url=sp.get("permalink") or f"{BASE}/produkt/{sp.get('slug')}", source_id=str(sp.get("id")),
        extra={
            "wc_id": sp.get("id"), "slug": sp.get("slug"), "sku": sp.get("sku") or None, "categories": cats,
            "line": line, "in_stock": sp.get("is_in_stock"),
            "ingredients": z.group(1).strip() if z else None,
            "nut_flag": nut_flag(desc), "storage": "gekühlt (Kühlkette, Versand in Kühlbox)",
            "description": desc, "images": imgs,
            "price_note": "Preis je Packung inkl. MwSt. lt. WooCommerce Store API", "shipping_eur": SHIPPING_EUR,
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(id_slug_or_url: str, shop: list[dict] | None = None) -> Product | None:
    k = id_slug_or_url.strip().rstrip("/").split("/")[-1]
    sp = next((p for p in (shop if shop is not None else store_products()) if str(p.get("id")) == k or p.get("slug") == k), None)
    return to_product(sp) if sp else None


class WiesbauerGourmet(Adapter):
    id = "wiesbauer_gourmet"
    store = STORE
    homepage = BASE
    notes = ("Live: public WooCommerce Store API of Wiesbauer Gourmet Gastro GmbH (Reidling NÖ): Easy Kitchen heat-up "
             "dishes and Sous-Vide pre-cooked mains (Gulasch, Beuschel, Rinderbacken, Ente/Gans, Stelze, Spareribs, "
             "Tafelspitz) with price incl. MwSt., SKU, stock, nutrition per 100 g where printed, ingredients, photos; "
             "chilled delivery AT/DE (19,90 € < 150 €); GTIN from product-page JSON-LD with with_gtin=True "
             "(+1 request per meal); 3 requests per call otherwise")

    def fetch(self, category="ready-meals", limit=500, with_gtin=False):
        meals = [sp for sp in store_products() if is_meal(sp)][:limit]
        return [to_product(sp, page_gtin(sp.get("permalink")) if with_gtin and sp.get("permalink") else None)
                for sp in meals]

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
