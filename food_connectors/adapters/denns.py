"""denn's BioMarkt Österreich — live connector for the public weekly offer feed (Angebote).

Access path (no login, no cookies, no browser): the Gatsby page-data JSON that denns-biomarkt.at itself loads
  https://www.denns-biomarkt.at/page-data/angebote/page-data.json
robots.txt (denns-biomarkt.at / biomarkt.de): 'User-agent: * Allow: /' (checked 2026-10-13).
result.data.sanityAllOffers.nodes + noLimitOffers.nodes = current AT offers (land=at) with denn's article number
(itemno), brand, title, pack (subtitle, may be a range for multi-variant offers), offer price (price), regular shelf
price (priceb), unit price text (pricec), validity, vegan/vegetarian flags and the official product image
(images.dennree.de/fitinto/576x384/<itemno>.top.png). Only promo offers (~80/week) — not the full assortment,
no GTIN, no nutrition. Use `off` (Open Food Facts, stores tag denn-s-biomarkt) for nutrition.

T2336 (2026-10-16) additions, same polite gate:
* `new_products()` — 'Neu im Sortiment' page-data (denns-biomarkt.at/page-data/neu-im-sortiment/page-data.json,
  newProductFeatures, isInAustria flag): brand, title, pack, regular shelf price, €/kg, official Sanity image.
* dennree brand catalog — dennree is the own brand of the dennree group, operator of denn's BioMarkt (DE+AT).
  www.dennree.de (TYPO3; robots `*` disallows only /typo3/, /typo3conf/, /*?id=* — so the '/productreload?id=…'
  ajax is NOT used; only category + product pages). Product page: name, Inhalt (net weight), Verkehrsbezeichnung,
  Zutaten, Nährwerte per 100 g, packshot images.dennree.de/fitinto/<WxH>/<denn's article no>.front.png.
  No price and no GTIN are published there; AT availability per article is not stated (DE brand site).
"""
from __future__ import annotations
import re
from ..http import get
from ..schema import Product
from .base import Adapter

FEED = "https://www.denns-biomarkt.at/page-data/angebote/page-data.json"
PAGE = "https://www.denns-biomarkt.at/angebote/"
MEAL_WORDS = ("suppe", "eintopf", "gulasch", "fertig", "fingerfood", "nuggets", "pizza", "lasagne", "curry", "risotto",
              "knödel", "strudel", "pudding", "dessert", "maultasche", "bowl", "falafel", "antipasti", "chili")

def _eur(s):
    if s in (None, ""): return None
    m = re.search(r"\d+(?:,\d+)?", str(s)); return float(m.group(0).replace(",", ".")) if m else None

def _size(s):
    """Single pack size in g/ml; None for ranges/variants ('350 g / 380 g', '185 g - 200 g') or pieces."""
    s = (s or "").replace("je ", "").strip()
    m = re.fullmatch(r"(\d+(?:,\d+)?)\s*(g|kg|ml|l)", s, re.I)
    if not m: return None
    v = float(m.group(1).replace(",", ".")); return round(v * 1000) if m.group(2).lower() in ("kg", "l") else round(v)

def _ppu(s):
    m = re.match(r"\s*1\s*(kg|l)\s*=\s*(\d+(?:,\d+)?)\s*$", s or "", re.I)
    return (float(m.group(2).replace(",", ".")), m.group(1).lower()) if m else (None, None)

def offers(raw: dict | None = None) -> list[dict]:
    d = (raw or get(FEED, timeout=30))["result"]["data"]
    out, seen = [], set()
    for k in ("sanityAllOffers", "noLimitOffers"):
        for n in (d.get(k) or {}).get("nodes") or []:
            key = n.get("_id") or (n.get("itemno"), n.get("title"))
            if key in seen or n.get("land") != "at" or n.get("hidden"): continue
            seen.add(key); out.append(n)
    return out

def to_product(n: dict) -> Product:
    ppu, unit = _ppu(n.get("pricec"))
    img = (n.get("image") or "").split("?")[0] or None
    brand = (n.get("brand") or "").strip() or None
    title = (n.get("title") or "").replace("❄", "").strip()
    pg = ((n.get("articleGroup") or {}).get("productGroup") or {}).get("title")
    offer, regular = _eur(n.get("price")), _eur(n.get("priceb"))
    return Product(source="denns", store="denn's BioMarkt", name=f"{brand or ''} {title}".strip(), brand=brand,
        price_eur=offer, unit_price_eur=ppu, unit=unit, size_g=_size(n.get("subtitle")), ean=None, image_url=img,
        category=pg, source_url=PAGE, source_id=n.get("itemno"),
        extra={"offer_price_eur": offer, "regular_price_eur": regular, "unit_price_text": n.get("pricec"), "pack": n.get("subtitle"),
               "valid_from": n.get("validfrom"), "valid_to": n.get("validto"), "app_price_eur": _eur(n.get("priceApp")),
               "frozen": "❄" in (n.get("title") or ""), "vegan": n.get("vegan"), "vegetarian": n.get("vegetarian"),
               "lactosefree": n.get("lactosefree"), "glutenfree": n.get("glutenfree"), "offer_type": n.get("angebotsart"),
               "price_from": bool(n.get("priceAb")), "markets_n": len(set((n.get("marketIdList") or {}).get("marketIds") or [])),
               "price_basis": "Aktionspreis (offer) in price_eur; regular_price_eur = Normalpreis", "feed": FEED})

def is_ready_meal(p: Product) -> bool:
    t = (p.name or "").lower()
    return any(w in t for w in MEAL_WORDS)

NEW_FEED = "https://www.denns-biomarkt.at/page-data/neu-im-sortiment/page-data.json"
NEW_PAGE = "https://www.denns-biomarkt.at/neu-im-sortiment/"
DENNREE = "https://www.dennree.de"
# dennree catalog categories that hold finished / ready-to-heat dishes (Tütensuppe = dry mix, excluded)
DENNREE_MEAL_CATS = ("pizza", "flammkuchen", "veg-bratlinge--pfannengerichte")
DENNREE_EXCLUDED_CATS = {"tuetensuppe": "Trockenmischung (Tütensuppe)", "bruehen": "Brühe (Zutat)",
                         "tomatenprodukte": "Sauce/Sugo (Komponente)"}

def new_products(raw: dict | None = None) -> list[Product]:
    d = (raw or get(NEW_FEED, timeout=30))["result"]["data"]
    out = []
    for n in (d.get("newProductFeatures") or {}).get("nodes") or []:
        if not n.get("isInAustria"): continue
        ppu, unit = _ppu((n.get("pricec") or "").strip())
        img = ((((n.get("offerImage") or {}).get("image") or {}).get("asset") or {}).get("url"))
        brand = (n.get("brand") or "").strip() or None
        title = (n.get("title") or "").strip()
        pg = ((n.get("articleGroup") or {}).get("productGroup") or {}).get("title")
        out.append(Product(source="denns", store="denn's BioMarkt", name=f"{brand or ''} {title}".strip(), brand=brand,
            price_eur=_eur(n.get("price")), unit_price_eur=ppu, unit=unit, size_g=_size(n.get("subtitle")), image_url=img,
            category=pg, source_url=NEW_PAGE,
            extra={"pack": (n.get("subtitle") or "").strip(), "unit_price_text": (n.get("pricec") or "").strip(),
                   "description": n.get("shordesc"), "labels": [l.get("title") for l in n.get("labels") or []],
                   "price_basis": "Regalpreis 'Neu im Sortiment' (AT, isInAustria)", "feed": NEW_FEED}))
    return out

def _txt(html_s: str) -> str:
    import html as _h
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", html_s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", t))).replace("\xa0", " ").strip()

def dennree_list(category: str, html_s: str | None = None) -> list[dict]:
    """Product teasers of one dennree.de catalog (sub)category page: url, name, denn's article no."""
    url = f"{DENNREE}/dennree-produkte/uebersicht/{category}"
    s = html_s if html_s is not None else get(url, raw=True).decode("utf-8", "replace")
    out, seen = [], set()
    for m in re.finditer(r'<a href="(/dennree-produkte/uebersicht/[a-z0-9-]+/[a-z0-9-]+)"><span class="teaserImage"><img src="[^"]*/(\d{6})\.front\.png[^"]*"[^>]*alt="([^"]*)"', s):
        if m.group(1) in seen: continue
        seen.add(m.group(1)); out.append({"url": DENNREE + m.group(1), "itemno": m.group(2), "name": re.sub(r"\s+", " ", m.group(3)).strip(), "category": category})
    return out

_NUT = (("kcal", r"Brennwert\s*([\d.,]+)\s*kJ\s*/\s*([\d.,]+)\s*kcal"), ("fat", r"Fett\s*([\d.,<]+)\s*g"),
        ("satfat", r"davon ges(?:\.|ättigte)\s*Fetts(?:\.|äuren)\s*([\d.,<]+)\s*g"), ("carbs", r"Kohlenhydrate\s*([\d.,<]+)\s*g"),
        ("sugar", r"davon Zucker\s*([\d.,<]+)\s*g"), ("fiber", r"Ballaststoffe\s*([\d.,<]+)\s*g"),
        ("protein", r"Eiweiß\s*([\d.,<]+)\s*g"), ("salt", r"Salz\s*([\d.,<]+)\s*g"))

def _num(x):
    x = (x or "").replace("<", "").replace(",", ".").strip()
    try: return float(x)
    except ValueError: return None

def atwater_ok(n: dict, tol: float = 0.12) -> bool | None:
    if not all(k in n for k in ("kcal", "fat", "carbs", "protein")): return None
    est = 9 * n["fat"] + 4 * n["carbs"] + 4 * n["protein"] + 2 * n.get("fiber", 0)
    return abs(est - n["kcal"]) <= max(15, tol * n["kcal"])

def dennree_product(url: str, html_s: str | None = None) -> Product | None:
    s = html_s if html_s is not None else get(url, raw=True).decode("utf-8", "replace")
    t = _txt(s)
    img = re.search(r'https://images\.dennree\.de/fitinto/\d+x\d+/(\d{6})\.front\.png', s)
    if not img: return None
    itemno = img.group(1)
    h1 = re.search(r"<h1>([^<]+)</h1>", s)
    if not h1: return None
    i = t.find("zurück zur Übersicht")
    if i < 0: return None
    t = "§ " + _txt(h1.group(1)) + " " + t[i:]
    m = re.search(r"§ (.+?) zurück zur Übersicht (.*?) Inhalt ([\d.,]+\s*(?:g|kg|ml|l)) Verkehrsbezeichnung (.+?) Zutaten: (.+?)(?: Hinweise (.+?))? Nährwerte (.+?)(?: Hauptnavigation|$)", t)
    if not m: return None
    name, desc, inhalt, denom, ingr, hints, nut_t = (g.strip() if g else None for g in m.groups())
    nut = {}
    for k, rx in _NUT:
        mm = re.search(rx, nut_t)
        if mm: nut[k] = _num(mm.group(2) if k == "kcal" else mm.group(1))
    nut = {k: v for k, v in nut.items() if v is not None}
    ok = atwater_ok(nut)
    if ok is False: nut_kept = {}
    else: nut_kept = nut
    cat = url.rstrip("/").split("/")[-2]
    return Product(source="denns", store="denn's BioMarkt", name=f"dennree {name}", brand="dennree", size_g=_size(inhalt),
        nutrition_100g=nut_kept, image_url=f"https://images.dennree.de/fitinto/576x384/{itemno}.front.png",
        producer="dennree GmbH", category=cat, source_url=url, source_id=itemno,
        extra={"denomination": denom, "ingredients": ingr, "notes": hints, "description": desc, "net_qty": inhalt,
               "frozen": "tiefgekühlt" in (denom or "").lower() or "tiefgefroren" in (denom or "").lower(),
               "nutrition_raw": nut, "atwater_ok": ok, "nutrition_basis": "100 g/ml (dennree.de Nährwerte)",
               "price_basis": "kein Preis veröffentlicht (Markenkatalog dennree.de)",
               "availability": "dennree-Eigenmarke (DE-Markenseite); AT-Verfügbarkeit je Artikel nicht angegeben"})

# images.dennree.de serves a grey 'BILD FOLGT' PNG (HTTP 200) when no packshot exists — md5 of that placeholder:
PLACEHOLDER_MD5 = {"28a3381472ca8bbd0718659b468f92e8"}

def is_placeholder(img_bytes: bytes) -> bool:
    import hashlib
    return hashlib.md5(img_bytes).hexdigest() in PLACEHOLDER_MD5

def dennree_catalog(categories=DENNREE_MEAL_CATS, verify_images: bool = True) -> list[Product]:
    out = []
    for c in categories:
        for it in dennree_list(c):
            p = dennree_product(it["url"])
            if not p: continue
            if verify_images and p.image_url:
                try: ph = is_placeholder(get(p.image_url, raw=True))
                except Exception: ph = None
                p.extra["image_check"] = "placeholder 'BILD FOLGT'" if ph else ("ok" if ph is False else "unreachable")
                if ph is not False: p.image_url = None
            out.append(p)
    return out

LUNCH_FEED = "https://www.denns-biomarkt.at/page-data/{market}/mittagsgerichte/page-data.json"
LINZ_MARKETS = ("linz-kaisergasse-17", "linz-landstr-111")

def lunch_menu(market: str = "linz-kaisergasse-17", raw: dict | None = None) -> list[dict]:
    """In-store bistro lunch menu ('Mittagsgerichte') of one denn's AT market: dish, side, price, day, diet flags.
    Freshly cooked counter dishes (not packaged products, no pack size/EAN/nutrition) — kept out of products.csv."""
    url = LUNCH_FEED.format(market=market)
    d = (raw or get(url, timeout=30))["result"]["data"]
    out = []
    for key in ("allSanityLunchOffer", "nextLunchOffer"):
      for node in (d.get(key) or {}).get("nodes") or []:
        for it in node.get("menuItems") or []:
            out.append({"market": market, "week": node.get("week"), "year": node.get("year"), "next_week": key == "nextLunchOffer", "dish": (it.get("title") or "").strip(), "side": (it.get("subtitle") or "").strip() or None,
                        "price_eur": it.get("price"), "day": (it.get("day") or "")[:10] or None, "all_week": bool(it.get("allweek")),
                        "vegan": it.get("vegan"), "vegetarian": it.get("vegetarian"), "lactosefree": it.get("lactosefree"),
                        "glutenfree": it.get("glutenfree"), "source_url": url})
    return out

class Denns(Adapter):
    id = "denns"; store = "denn's BioMarkt"; homepage = "https://www.denns-biomarkt.at"; status = "live"
    notes = ("Live: denn's BioMarkt AT weekly offers via the public Gatsby page-data JSON (robots Allow: /, no login/cookies): "
             "denn's article no., brand, pack, offer + regular price, €/kg, validity, vegan flags, official image (images.dennree.de). "
             "Offers only (~80/week), no GTIN/nutrition — combine with `off` (stores tag denn-s-biomarkt). "
             "Also: --category neu (Neu im Sortiment, AT shelf price) and --category eigenmarke (dennree brand catalog "
             "dennree.de: net weight, ingredients, nutrition/100 g, packshot by denn's article no.; no price/GTIN).")
    def search(self, q: str, limit: int = 20) -> list[Product]:
        ql = q.lower(); ps = [to_product(n) for n in offers()]
        return [p for p in ps if ql in f"{p.name} {p.category or ''}".lower()][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 200) -> list[Product]:
        if category == "eigenmarke": return dennree_catalog()[:limit]
        if category == "neu": return new_products()[:limit]
        ps = [to_product(n) for n in offers()]
        if category == "ready-meals": ps = [p for p in ps if is_ready_meal(p)]
        elif category != "all": ps = [p for p in ps if category.lower() in f"{p.name} {p.category or ''}".lower()]
        return ps[:limit]
