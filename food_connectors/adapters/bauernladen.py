"""Bauernladen.at — Austrian farm-direct marketplace, category 'Schnelle Küche' (jar/heat-up meals) — live connector.

Marketplace: https://bauernladen.at (producers sell and ship themselves; each product page states the producer's own
'Warenübergabe & Lieferkonditionen' — shipping fee, free-shipping threshold, accepted countries). Products are sold by
the producer, so `brand` / `producer` = the farm or manufactory named in the product JSON-LD `brand` + `offers.seller`,
and the producer seat is the address printed in the producer box of the page.

Access path (no login, no cookies, no cart, no JS):
  listing  https://bauernladen.at/produkte/liste/lebensmittel/schnelle-kueche[/<page>]  (server-rendered, 4 pages / 79
           products on 2026-10-18) → absolute product URLs /produkte/<producer-slug>/<product-slug>-<id>
  product  the product page: schema.org Product JSON-LD (name, sku = product id, brand, description = Zutaten text,
           category path, images, Offer/AggregateOffer price + availability + seller) + the visible 'Kaufen' line
           (pack size e.g. '320 g € 9,90 30,94 € / Kilo'), the producer address box, the producer's delivery conditions
           and the 'Produktinformationen' flags (Bio, Vegan, Vegetarisch, Kühlbedürftig, Tiefgekühlt, Haltbarkeit in Tagen).
robots.txt: User-agent * — only /cgi-bin/, /contact?to=* and the order forms /produkte/form-* are disallowed.
All requests go through the food-connectors polite gate (robots + 1 req/s per host).
No GTIN is published. A few producers print a 'Nährwerte' line without a reference quantity → kept verbatim in
extra.nutrition_text only, never mapped to per-100 g values.
"""
from __future__ import annotations
import html as _html, json, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://bauernladen.at"
LIST = BASE + "/produkte/liste/lebensmittel/schnelle-kueche"
STORE = "Online: Bauernladen.at"
URL_RE = re.compile(r"https://bauernladen\.at/produkte/([a-z0-9-]+)/([a-z0-9-]+)-(\d+)\b")
PAGE_RE = re.compile(r'href="/produkte/liste/lebensmittel/schnelle-kueche/(\d+)"')
# not a heat-up dish: broths/fonds, sauces/sugo, sides, dumplings, desserts, cold cuts, boxes, powders
NOT_MEAL_RE = re.compile(r"fond\b|klare\s|kräftige\s.*suppe|rindsuppe|sugo|soße|sosse|bolo(g)?nese|knödel|sauerkraut|"
                         r"rotkraut|gratin|zelten|holler|box\b|protein|pulver|lungenstrudel|sülz|letscho|gutschein|^bio sauce|sauce$", re.I)
SIZE_RE = re.compile(r"Kaufen\s+(?:Wählen Sie eine Menge aus:\s*)?(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|Stk\.)\s", re.I)
FLAG_KEYS = ("Bio", "Vegan", "Vegetarisch", "Glutenfrei", "Laktosefrei", "Kühlbedürftig", "Tiefgekühlt")


def _txt(s: str | None) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse_listing(html: str) -> tuple[list[dict], int]:
    seen, out = set(), []
    for m in URL_RE.finditer(html):
        if m.group(3) in seen: continue
        seen.add(m.group(3)); out.append({"id": m.group(3), "producer_slug": m.group(1), "url": m.group(0)})
    pages = [int(p) for p in PAGE_RE.findall(html)]
    return out, max(pages or [1])


def is_meal_name(name: str | None) -> bool:
    return bool(name) and not NOT_MEAL_RE.search(name.strip())


def _ld_product(html: str) -> dict:
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try: j = json.loads(m)
        except Exception: continue
        if isinstance(j, dict) and j.get("@type") == "Product": return j
    return {}


def _size(T: str) -> tuple[float | None, str | None]:
    m = SIZE_RE.search(T)
    if not m: return None, None
    v, u = float(m.group(1).replace(",", ".")), m.group(2).lower()
    if u in ("kg", "l"): return v * 1000, ("g" if u == "kg" else "ml")
    if u.startswith("stk"): return None, "Stk"
    return v, u


def parse_product(html: str, url: str | None = None) -> Product | None:
    ld = _ld_product(html)
    if not ld.get("name"): return None
    of = ld.get("offers") or {}
    if isinstance(of, list): of = of[0] if of else {}
    price = of.get("price") if of.get("@type") != "AggregateOffer" else of.get("lowPrice")
    T = _txt(html)
    size, unit = _size(T)
    if size is None:  # 'Stk' offers: take the net content printed in the product name ('- 440ml', 'ca. 480g')
        nm = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|ml)\b", ld["name"], re.I)
        if nm: size, unit = float(nm.group(1).replace(",", ".")), nm.group(2).lower()
    flags = {}
    info = re.search(r"Produktinformationen (.{0,700})", T)
    for k in FLAG_KEYS:
        f = re.search(rf"\b{k}: (Ja|Nein)", info.group(1)) if info else None
        flags[k.lower()] = None if not f else f.group(1) == "Ja"
    state = re.search(r"Verarbeitungszustand: (\w+)", info.group(1)) if info else None
    days = re.search(r"Haltbarkeit in Tagen ca\.: (\d+)", T)
    lief = re.search(r"Lieferkonditionen: (.+?)(?: \.destination-countries| Bewertungen ★| Produktinformationen)", T)
    pickup = "Abholung beim Produzenten" in T
    addr = None
    i = T.find("Fragen an den Betrieb")
    if i > 0:  # producer box: '<name> [+43 phone] <street> <PLZ> <Ort> <Bundesland>' (after the e-mail obfuscation script)
        pre = re.split(r"//\]\]>|\+\d{2}[\d ]{6,}\d", T[max(0, i - 220):i])[-1].strip()
        addr = re.match(r"(.{3,120})", pre) if re.search(r"\b\d{4}\b", pre) else None
    nut = re.search(r"Nährwerte:?\s*(.{10,300}?)(?: Kaufen | Allergene|$)", T)
    u = of.get("url") or url
    m = URL_RE.search(u or "")
    imgs = ld.get("image") or []
    if isinstance(imgs, str): imgs = [imgs]
    seller = (of.get("seller") or {}).get("name") or ld.get("brand")
    countries = re.search(r"ausschließlich aus folgenden Ländern an: ([^.]+)\.", lief.group(1)) if lief else None
    return Product(source="bauernladen", store=STORE, name=_html.unescape(ld["name"]).strip(), brand=ld.get("brand"),
        price_eur=float(price) if price not in (None, "") else None, unit=unit, size_g=size if unit in ("g", "ml") else None,
        ean=None, image_url=imgs[-1] if imgs else None, producer=seller,
        origin="AT" + (f" ({addr.group(1).strip()})" if addr else ""), category=ld.get("category"),
        source_url=u, source_id=str(ld.get("sku") or (m.group(3) if m else "")) or None,
        extra={"producer_slug": m.group(1) if m else None, "producer_address": addr.group(1).strip() if addr else None,
               "ingredients_text": (ld.get("description") or "").strip() or None,
               "availability": str(of.get("availability") or "").rsplit("/", 1)[-1] or None,
               "pack_unit": unit, "flags": flags, "state": state.group(1) if state else None,
               "shelf_life_days": int(days.group(1)) if days else None,
               "delivery_terms": lief.group(1).strip() if lief else None, "ships_to": countries.group(1).strip() if countries else None,
               "pickup_option": pickup, "nutrition_text": nut.group(1).strip() if nut else None,
               "nutrition_note": "keine GTIN; Nährwerte nur als Freitext ohne Bezugsgröße (nicht auf 100 g umgerechnet)",
               "images": imgs, "rating": (ld.get("aggregateRating") or {}).get("ratingValue")})


def product(url: str) -> Product | None:
    if not URL_RE.search(url or ""): return None
    return parse_product(get(url, raw=True, timeout=40).decode("utf-8", "replace"), url)


class Bauernladen(Adapter):
    id = "bauernladen"; store = STORE; homepage = BASE; status = "live"
    notes = ("Live: bauernladen.at marketplace, category 'Schnelle Küche' (farm/manufactory jar and heat-up meals; each producer "
             "ships itself within AT, terms on every product page). Server-rendered listing → product JSON-LD + pack size + producer "
             "address + delivery terms (robots allow; polite 1 req/s; no login/cart). No GTIN; nutrition only as unreferenced free text.")
    def tiles(self) -> list[dict]:
        first, n = parse_listing(get(LIST, raw=True, timeout=40).decode("utf-8", "replace"))
        out = list(first)
        for p in range(2, n + 1):
            more, _ = parse_listing(get(f"{LIST}/{p}", raw=True, timeout=40).decode("utf-8", "replace"))
            out += [t for t in more if t["id"] not in {x["id"] for x in out}]
        return out
    def _all(self) -> list[Product]:
        return [p for p in (product(t["url"]) for t in self.tiles()) if p]
    def search(self, q: str, limit: int = 10) -> list[Product]:
        words = re.findall(r"\w{3,}", q.lower())
        hits = [t for t in self.tiles() if all(w in t["url"].lower() for w in words)] or self.tiles()
        out = []
        for t in hits:
            p = product(t["url"])
            if p and all(w in (p.name + " " + (p.brand or "")).lower() for w in words): out.append(p)
            if len(out) >= limit: break
        return out
    def fetch(self, category: str = "ready-meals", limit: int = 100) -> list[Product]:
        ps = self._all()
        if category == "ready-meals": ps = [p for p in ps if is_meal_name(p.name)]
        return ps[:limit]


# --- producer-side nutrition (T1509) -------------------------------------------------------------------------------
# fairkocht gmbh (Andelsbuch, Vbg) sells on Bauernladen without nutrition, but its own WooCommerce shop prints
# 'Nährwerte je 100 g: ENERGIE x kJ / y kcal FETT … EIWEISS … SALZ …' in the public Store API description.
FAIRKOCHT_API = "https://www.fairkocht.at/wp-json/wc/store/v1/products?per_page=100"


def _g(label: str, blk: str) -> float | None:
    m = re.search(label + r"\D{0,40}?(\d+(?:,\d+)?)\s*g", blk, re.I)
    return float(m.group(1).replace(",", ".")) if m else None


def fairkocht_nutrition(products: list[dict] | None = None) -> dict[str, dict]:
    """name → {kcal_100, fat_100, satfat_100, carbs_100, sugar_100, protein_100, salt_100, price_eur, size, url,
    atwater_ok}. Only values printed 'je 100 g'; rows whose kcal disagree with the macros by >15 % get atwater_ok=False
    (e.g. Paprikahendl 19 kcal vs 55 from macros) and must not be used."""
    if products is None:
        r = get(FAIRKOCHT_API)
        products = json.loads(r) if isinstance(r, (str, bytes)) else r
    out = {}
    for p in products:
        t = _txt((p.get("description") or "") + " " + (p.get("short_description") or ""))
        i = t.find("Nährwerte je 100 g")
        if i < 0:
            continue
        blk = t[i:i + 400]
        k = re.search(r"(\d+)\s*kJ\s*/\s*(\d+)\s*kcal", blk)
        if not k:
            continue
        v = {"kcal_100": float(k.group(2)), "fat_100": _g("FETT", blk), "satfat_100": _g("gesättigte Fettsäuren", blk),
             "carbs_100": _g("KOHLENHYDRATE", blk), "sugar_100": _g("Zucker", blk), "protein_100": _g("EIWEISS", blk),
             "salt_100": _g("SALZ", blk)}
        atw = 4 * (v["protein_100"] or 0) + 9 * (v["fat_100"] or 0) + 4 * (v["carbs_100"] or 0)
        v["atwater_ok"] = abs(atw - v["kcal_100"]) / v["kcal_100"] < 0.15 or (v["kcal_100"] < 30 and abs(atw - v["kcal_100"]) < 6)
        size = re.search(r"Größe:\s*(\d+\s*(?:ml|g))", t)
        v.update(price_eur=int(p["prices"]["price"]) / 100, size=size.group(1) if size else None, url=p.get("permalink"))
        out[_html.unescape(p["name"])] = v
    return out
