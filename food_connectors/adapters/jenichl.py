"""Genussbauernhof Jenichl (Altheim, Innviertel OÖ) — live connector.

Shop: www.genussbauernhof-jenichl.at/shop (Webflow site + embedded Ecwid store 34077132). Impressum: 'Genussbauernhof
Jenichl, Wagham 1, A-4950 Altheim, Ansprechpartner Herr Franz Jenichl, Gesellschaftsform: Einzelunternehmen,
Medieninhaber Franz & Brigitte Jenichl, Unternehmensgegenstand Direktvermarktung, Ab-Hof-Verkauf' — no UID, no
Firmenbuch number published (farm sole trader), no GLEIF/LEI record (fulltext 'Jenichl' = 0 hits, 2026-10-25).
Shipping (/zahlung-versand): 'Lieferung im Inland (Österreich) … Versand durch Österreichische Post AG, gestaffelt nach
Gewicht: bis 20 kg EUR 11,50, bis 40 kg EUR 17,90, ab 40 kg EUR 35,00'; delivery 2–4 working days; pickup at the farm
or at the Bauernmarkt Weberzeile Ried free → Linz is inside the delivery area.

Access path (no login, no cookies, no cart, no JS), ONE request for the whole catalogue:
  POST https://eu-fra3-storefront-api.ecwid.com/storefront/api/v1/34077132/catalog
       {"categoryViewMode": "EXPANDED", "parentCategoryId": 0, "pagination": {"offset": 0, "limit": 100}}
  — the same unauthenticated JSON the public shop widget loads (name, price incl. 10 % USt., 30-day lowest price,
  description with 'Zutaten' + allergens in capitals + net weight 'Im Glas | 390g', sold-out flag, media items).
  Single product: POST …/catalog/product {"productIdentifier": {"type": "PUBLISHED", "productId": <id>}}.
robots.txt: the shop site has none (Webflow 404 → allow); the storefront-api host has no robots.txt (404 → allow).
All requests go through the food-connectors polite gate (robots + 1 req/s per host).

Meals: 4 heat-up jar meals 'essfertig' (Gulasch im Glas 390 g, Gulaschsuppe 390 g, Gefüllte Paprika mit Tomatensauce
640 g, Beuschel 390 g; 'Vor dem Verzehr erwärmen!') and 7 frozen Knödel packs (Innviertler Surspeck-, Selchfleisch-,
Haschee-, Grammel-, Spinat-, Bärlauchknödel 10 Stk., Tiroler Knödel 4 Stk.; '12–15 Minuten in siedendes Wasser').
Excluded: Gulaschsaft, Pasta Asciutta Sugo, Chili Dip (sauces), plain Semmelknödel (side), Speck/Geselchtes, sausages,
Leberkäse, spreads, Sulz.
Photos (vision-checked 2026-10-25): jar meals = real photos of the labelled jar (Gulasch: the shop's main image shows a
'Gulaschsaft' jar in front, so the 2nd picture with the 'Gulasch essfertig' label is used); Surspeck-, Spinat-,
Bärlauch- and Tiroler Knödel have their own plate photo; Haschee-, Grammel- and Selchfleischknödel share one identical
plate photo that does not show the filling → image_url None (photo kept in extra.shared_image_url).
No GTIN and no nutrition table are published → empty, never estimated.
"""
from __future__ import annotations
import html as _html, json, re, urllib.request
from .base import Adapter
from ..http import UA
from ..polite import polite_urlopen
from ..schema import Product

BASE = "https://www.genussbauernhof-jenichl.at"
STORE_ID = "34077132"
API = f"https://eu-fra3-storefront-api.ecwid.com/storefront/api/v1/{STORE_ID}"
STORE = "Online: Genussbauernhof Jenichl"
SHIPPING = {"area": "Österreich (Österreichische Post AG)", "fee_eur": 11.5, "fee_eur_to_40kg": 17.9, "fee_eur_over_40kg": 35.0,
            "pickup": "Hof Wagham 1, 4950 Altheim / Bauernmarkt Weberzeile Ried (kostenlos)",
            "source": BASE + "/zahlung-versand"}
# not a dish: sauces/dips, cooking juice, plain side dumplings, cured meat, sausages, spreads, aspic
NOT_MEAL_RE = re.compile(r"saft|sugo|dip|semmelkn|speck$|geselcht|w(ü|u)rst|wiener|polnische|alpenl|knacker|frankfurter|"
                         r"depreziner|leberk(ä|a)se|aufstrich|pastete|schmalz|sulz|gutschein", re.I)
IMAGE_INDEX = {"241886285": 1}                       # Gulasch: 2nd picture shows the 'Gulasch essfertig' jar
SHARED_IMAGE = {"242801295", "242801421", "242950152"}  # Haschee/Grammel/Selchfleisch: same generic plate photo


def _txt(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>|</p>|</div>", "\n", s or "")
    return re.sub(r"[ \t\r\f\v]+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def is_meal_name(name: str | None) -> bool:
    return bool(name) and not NOT_MEAL_RE.search(name.strip())


def products_from_catalog(d: dict) -> list[dict]:
    out = []
    for c in (d or {}).get("expandedCategories") or []:
        out += c.get("products") or []
    return out


def parse_product(d: dict) -> Product | None:
    if not d or not d.get("name"): return None
    name = re.sub(r"\s*;\s*", " – ", d["name"].strip())
    pid = str((d.get("identifier") or {}).get("productId") or "")
    o = d.get("defaultOptionsOverrides") or {}
    pr = o.get("pricesOverrides") or {}
    var = o.get("variationOverrides") or {}
    desc = _txt(d.get("description"))
    zut = re.search(r"Zutaten:\s*(.+?)(?:\s+(?:Vor dem Verzehr|Die tiefgek(?:ü|u)hlten|Im Glas\s*\|)|$)", desc, re.S)
    zut = re.sub(r"\s+", " ", zut.group(1)).strip() if zut else None
    allerg = sorted(set(re.findall(r"\b[A-ZÄÖÜ]{4,}\b", zut or ""))) or None
    g = re.search(r"Im Glas\s*\|\s*(\d+)\s*g", desc)
    pieces = re.search(r"\((\d+)\s*Stk\.?\)", name)
    frozen = bool(re.search(r"tiefgek(ü|u)hlt", desc, re.I))
    pics = [m for m in var.get("mediaItems") or [] if m.get("type") == "PICTURE"]
    idx = IMAGE_INDEX.get(pid, next((i for i, m in enumerate(pics) if m.get("isMain")), 0))
    img = (pics[idx].get("image1500pxUrl") or pics[idx].get("image800pxUrl")) if len(pics) > idx else None
    shared = None
    if pid in SHARED_IMAGE: shared, img = img, None
    taxes = pr.get("appliedTaxes") or []
    kind = (desc.split("|")[0].strip() if "|" in desc else None)
    return Product(source="jenichl", store=STORE, name=name, brand="Genussbauernhof Jenichl",
        price_eur=pr.get("basePriceWithModifiersDiscountAndTaxes"), unit="Glas" if g else "Packung",
        size_g=float(g.group(1)) if g else None, ean=None, image_url=img, producer="Genussbauernhof Jenichl (Franz & Brigitte Jenichl)",
        origin="AT (Altheim, Innviertel OÖ)", category="Tiefkühl-Knödel" if frozen else "Fertiggerichte im Glas",
        source_url=((d.get("urls") or {}).get("directPageUrl")) or f"{BASE}/shop#!/p/{pid}", source_id=pid or None,
        extra={"ingredients": zut, "allergens_marked": allerg, "description": desc, "kind": kind,
               "pieces": int(pieces.group(1)) if pieces else None, "frozen": frozen,
               "storage": "tiefgekühlt (lt. Shop)" if frozen else "Glas, essfertig – vor dem Verzehr erwärmen (lt. Shop)",
               "sold_out": bool(var.get("isSoldOut")), "vat_percent": taxes[0].get("percent") if taxes else None,
               "lowest_30d": (pr.get("lowestPrice") or {}).get("labelForProductList"),
               "shared_image_url": shared, "image_kind": "jar photo (printed label)" if (img and g) else ("plate photo" if img else None),
               "shipped_weight_kg": (var.get("weight") or {}).get("value"),
               "nutrition_note": "genussbauernhof-jenichl.at veröffentlicht keine Nährwerte/GTIN — nicht geschätzt",
               "price_basis": "Preis inkl. 10 % USt. lt. Ecwid-Storefront; Post-Versand AT 11,50 € bis 20 kg",
               "shipping": SHIPPING})


def _post(path: str, body: dict, timeout: int = 40) -> dict | None:
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with polite_urlopen(req, timeout=timeout) as r: return json.loads(r.read())
    except Exception as e:
        if getattr(e, "code", None) in (400, 404, 410): return None
        raise


def catalog_json() -> dict | None:
    return _post("/catalog", {"categoryViewMode": "EXPANDED", "parentCategoryId": 0, "pagination": {"offset": 0, "limit": 100}})


def product(url_or_id: str) -> Product | None:
    m = re.search(r"/p/(\d+)", url_or_id) or re.fullmatch(r"\s*(\d+)\s*", url_or_id)
    if not m: return None
    d = _post("/catalog/product", {"productIdentifier": {"type": "PUBLISHED", "productId": int(m.group(1))}})
    if not d or not is_meal_name(d.get("name")): return None
    return parse_product(d)


class Jenichl(Adapter):
    id = "jenichl"; store = STORE; homepage = BASE + "/shop"; status = "live"
    notes = ("Live: genussbauernhof-jenichl.at (Genussbauernhof Jenichl, Franz & Brigitte Jenichl, Wagham 1, 4950 Altheim OÖ; "
             "Einzelunternehmen, no UID/FN published, no LEI). Ships Austria via Post (11,50 € up to 20 kg). Public Ecwid storefront "
             "catalog JSON (1 request; no robots on either host; polite 1 req/s; no login/cart). 4 heat-up jar meals + 7 frozen "
             "Knödel; price incl. USt., ingredients, allergens, weight, vision-checked photos. No GTIN/nutrition published.")
    def _all(self) -> list[Product]:
        return [p for p in (parse_product(x) for x in products_from_catalog(catalog_json())) if p]
    def search(self, q: str, limit: int = 10) -> list[Product]:
        words = re.findall(r"\w{3,}", q.lower())
        return [p for p in self._all() if is_meal_name(p.name)
                and all(w in (p.name + " " + (p.extra.get("ingredients") or "")).lower() for w in words)][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 60) -> list[Product]:
        ps = self._all()
        if category == "ready-meals": ps = [p for p in ps if is_meal_name(p.name)]
        return ps[:limit]
