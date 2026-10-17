"""ADAMAH BioHof (Glinzendorf, Marchfeld) — live connector for the ready meals in the adamah.at Bio-Shop.

Operator: ADAMAH Vertriebs GmbH, Sonnenweg 11, 2280 Glinzendorf; FN 554551t (LG Korneuburg), UID ATU76911656
(VIES valid, name + address match, 2026-10-17); Bio-Kontrollstelle AT-BIO-301. BioKistl home delivery in Wien,
parts of Niederösterreich and Burgenland (not Linz; konsument.at Kochbox-Test 2023 + food-connectors mealkits registry).

Access path (no login, no cookies, no session/anonymous-user call): adamah.at is an Angular shop; its front-end loads
products for every anonymous visitor from the shop's own JSON endpoints, which are used here unchanged:
  POST https://www.adamah.at/ACM/api/webshop/getproducts      {"searchCriteria": "<text>", "startIndex": 0, "numDataSets": N}
  POST https://www.adamah.at/ACM/api/webshop/getproductdetail {"productSid": <sid>}   (+ productInfo, contentDesc = Zutaten)
  GET  https://www.adamah.at/ACM/AttachmentLoader?rowguid=<picDetailRowguid>&width=400  (official product photo)
robots.txt (checked 2026-10-17): ``User-agent: * Allow: /``. Requests go through the food-connectors polite gate
(robots.txt enforced, ≥1 s per host). Cart / user / payment endpoints are never called.
adamah.at publishes NO nutrition table and NO GTIN for these items (``eanCode`` is a 5-digit internal PLU, never mapped
to ``ean``); those fields stay empty (never estimated). Category codes: 0841 'Fertiggerichte', 0275 'gekühlte
Fertiggerichte'; sauces/Sugo, Pasteten/Aufstriche, raw pasta, burger/schnitzel patties, desserts and broth are excluded.
"""
from __future__ import annotations
import html as _html, json, re, urllib.request
from .base import Adapter
from ..polite import polite_urlopen
from ..http import UA
from ..schema import Product

BASE = "https://www.adamah.at"
API = BASE + "/ACM/api/webshop/"
STORE = "Online: ADAMAH BioHof"
MEAL_CATEGORIES = {"0841", "0275"}
SEARCH_TERMS = ["Fertiggericht", "Weckglas", "Bistro", "Eintopf", "Gulasch", "Curry", "Lasagne", "Ragout", "Suppe",
                "Knödel", "Chili", "Rolle", "Röllchen", "Samosa", "Fleischbällchen", "Braten", "Paprikahendl"]
NOT_MEAL_RE = re.compile(r"sugo|sauce|soße|pastete|rillettes|aufstrich|burger|schnitzel|faschier|grünkern|lupinen|"
                         r"falafel|taler|tortellini|ravioli|nockerl|cheesecake|scheiterhaufen|semmelrolle|grillinge|"
                         r"bohnen gegart|klare suppe|brüh|würfel|paste\b", re.I)
MEAL_RE = re.compile(r"eintopf|gulasch|curry|suppe|knödel|lasagne|ragout|chili|braten|hendl|bällchen|rolle|röllchen|"
                     r"samosa|frühlingsrolle|bohnentopf|moussaka|risotto", re.I)

def _post(endpoint: str, body: dict, timeout: int = 90):
    req = urllib.request.Request(API + endpoint, data=json.dumps(body).encode(), method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"})
    with polite_urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"null")

def _txt(s: str | None) -> str | None:
    if not s: return None
    s = re.sub(r"<br\s*/?>|</p>|</h\d>", "\n", s)
    s = _html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t\r\f\v]+", " ", s).strip() or None

def image_url(p: dict) -> str | None:
    g = p.get("picDetailRowguid") or p.get("picPreviewRowguid")
    return f"{BASE}/ACM/AttachmentLoader?rowguid={g}&width=400" if g else None

def price(p: dict) -> float | None:
    pos = p.get("priceListPos") or []
    v = pos[0].get("singleUnitPrice") if pos else None
    return round(float(v), 2) if v is not None else None

def is_meal(p: dict) -> bool:
    n = p.get("name") or ""
    n_chk = re.sub(r"\bin \w*(sauce|soße)\b", "", n, flags=re.I)  # 'Fleischbällchen in Tomatensauce' is a dish, 'Hirschsugo' is not
    return p.get("category") in MEAL_CATEGORIES and bool(MEAL_RE.search(n)) and not NOT_MEAL_RE.search(n_chk)

def size_g(p: dict) -> tuple[float | None, str | None]:
    """Net content in g/ml. For '410 ml' jars of Biohof Achleitner the figure is the jar volume (content ca. 350 ml per
    biohof.at) → left empty with a note; never the jar volume."""
    unit = (p.get("unitDesc") or "").strip()
    nw = p.get("netWeight")
    if re.fullmatch(r"410\s*ml", unit) and (p.get("producer") or "").lower().startswith("biohof achleitner"):
        return None, "410 ml = Glasvolumen (Inhalt lt. biohof.at ca. 350 ml) → size_g leer"
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l)\b", p.get("name") or "")
    if m:
        v = float(m.group(1).replace(",", ".")); u = m.group(2).lower()
        return (v * 1000 if u in ("kg", "l") else v), "Menge aus dem Produktnamen"
    if nw: return float(nw), "netWeight lt. adamah.at"
    return None, None

def search_raw(q: str, limit: int = 500) -> list[dict]:
    return [p for p in (_post("getproducts", {"searchCriteria": q, "startIndex": 0, "numDataSets": limit}) or []) if p.get("sid")]

def detail_raw(sid: int | str) -> dict | None:
    d = _post("getproductdetail", {"productSid": int(sid)})
    return d if d and d.get("sid") else None

def to_product(p: dict) -> Product:
    size, note = size_g(p)
    zut = _txt(p.get("contentDesc"))
    if zut: zut = re.sub(r"^Zutaten:\s*", "", zut)
    bio = (p.get("marketingProjPriceList") or "").lower()
    return Product(source="adamah", store=STORE, name=p.get("name"), brand=p.get("producer"), price_eur=price(p),
        unit=p.get("unit"), size_g=size, ean=None, image_url=image_url(p), producer=p.get("producer"),
        origin=p.get("originPriceList"), category="Fertiggerichte" if p.get("category") == "0841" else "gekühlte Fertiggerichte",
        source_url=f"{BASE}/Produktdetailseite/{p.get('alias')}" if p.get("alias") else None, source_id=str(p.get("sid")),
        extra={"unit_desc": p.get("unitDesc"), "size_note": note, "ingredients": zut, "description": _txt(p.get("productInfo")),
               "bio_status": p.get("marketingProjPriceList"), "bio": True if bio == "kontrolliert biologisch" else (False if "nicht bio" in bio else None),
               "base_price": {"factor": p.get("basePriceFactor"), "unit": p.get("basePriceUnit")},
               "currently_not_available": p.get("currentlyNotAvailable"), "plu": p.get("eanCode"), "article_nr": p.get("articleNr"),
               "price_valid_from_ms": p.get("priceListPosFrom"), "tax_percent": p.get("taxPercent"),
               "nutrition_note": "adamah.at veröffentlicht keine Nährwerte/GTIN — nicht geschätzt (eanCode = interne PLU)",
               "price_basis": "Preis je Stück inkl. MwSt. lt. adamah.at Bio-Shop (Lieferung mit dem BioKistl; Glaspfand wo angegeben)",
               "delivery_area": "Wien, Teile NÖ und Burgenland (kein Linz)"})

def product(sid: str) -> Product | None:
    s = re.sub(r"\D", "", str(sid).rsplit("_", 1)[-1].split("-")[0])
    d = detail_raw(s) if s else None
    return to_product(d) if d else None

class Adamah(Adapter):
    id = "adamah"; store = STORE; homepage = BASE; status = "live"
    notes = ("Live: ADAMAH BioHof (adamah.at, ADAMAH Vertriebs GmbH, Glinzendorf; BioKistl delivery Wien/NÖ/Burgenland, "
             "not Linz). The shop's own anonymous product JSON (webshop/getproducts + getproductdetail; robots Allow: /; "
             "polite 1 req/s; no cart/user endpoints). Ready meals = categories 0841/0275 minus sauces/Pasteten/pasta/"
             "patties/desserts. Price, net weight, producer, origin, bio status, ingredients, official photo. No GTIN/nutrition.")
    def candidates(self, terms=None) -> list[dict]:
        seen: dict = {}
        for t in terms or SEARCH_TERMS:
            for p in search_raw(t):
                seen.setdefault(p["sid"], p)
        return list(seen.values())
    def search(self, q: str, limit: int = 10) -> list[Product]:
        return [to_product(p) for p in search_raw(q, 200)[:limit]]
    def fetch(self, category: str = "ready-meals", limit: int = 80) -> list[Product]:
        ps = self.candidates()
        if category == "ready-meals": ps = [p for p in ps if is_meal(p)]
        out = []
        for p in ps[:limit]:
            d = detail_raw(p["sid"]) or p
            out.append(to_product(d))
        return out
