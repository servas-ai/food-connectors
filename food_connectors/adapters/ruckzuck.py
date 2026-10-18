"""Ruck Zuck Laden — Dunzinger's 'Ruck Zuck Glasl' (Hirschbach im Mühlkreis, OÖ) — live connector.

Shop: www.ruckzuck-laden.at (Schimpl OG, Guttenbrunn 18, 4242 Hirschbach im Mühlkreis; FN 306047w LG Linz =
evi.gv.at 'Eingetragen', OG since 08.03.2008, Geschäftszweig 'Betrieb eines Gasthauses'; UID ATU64017307 VIES valid,
name+address match, checked 2026-10-18). Home page: 'Wir liefern unsere Gläser direkt zu dir nach Hause — Österreich ab
100 Euro, in Deutschland ab 150 Euro ohne Versandkosten, ansonsten 15 Euro' → Linz is inside the delivery area.
Jars are cooked in the jar ('direkt im Glas eingekocht') and keep unrefrigerated ('lange ungekühlt haltbar').

Access path (no login, no cookies, no cart, no JS):
  product ids  https://www.ruckzuck-laden.at/wp-sitemap-ecstore-1.xml  (WordPress sitemap of the Ecwid store)
  product      POST https://eu-fra4-storefront-api.ecwid.com/storefront/api/v1/102929329/catalog/product
               {"productIdentifier": {"type": "PUBLISHED", "productId": <id>}} — the same unauthenticated JSON the
               public storefront widget loads (name, price incl. 10 % MwSt., 30-day lowest price, description with
               Zutaten/allergens in capitals, ribbon, categories, sold-out flag, media items).
robots.txt: www.ruckzuck-laden.at disallows only /wp-admin/; the storefront-api host has no robots.txt (404 → allow).
All requests go through the food-connectors polite gate (robots + 1 req/s per host).

Photos: every dish has (a) a main 'serving' image and (b) a jar packshot on a white background with the printed dish
label ('Dunzinger's Ruck Zuck … Chili con carne'). The packshot is returned as image_url (vision-gated 7/7 on
2026-10-18: label name matches the article); the main image is kept in extra.serving_image_url only, because most
main images are photorealistic illustrations rather than photos of the product.
No GTIN (shop SKUs are internal) and no nutrition table are published → empty, never estimated. Net content is
stated only for a few jars (e.g. 'Erdäpfelgulasch 315 ml') → size_g empty, extra.volume_ml when stated.
"""
from __future__ import annotations
import html as _html, json, re, urllib.request
from .base import Adapter
from ..http import get, UA
from ..polite import polite_urlopen
from ..schema import Product

BASE = "https://www.ruckzuck-laden.at"
STORE_ID = "102929329"
SITEMAP = BASE + "/wp-sitemap-ecstore-1.xml"
API = f"https://eu-fra4-storefront-api.ecwid.com/storefront/api/v1/{STORE_ID}/catalog/product"
STORE = "Online: Ruck Zuck Laden (Dunzinger's)"
PID_RE = re.compile(r"<loc>(https://www\.ruckzuck-laden\.at/shop/[^<]*-p(\d+))/?</loc>")
# not a heat-up dish: clear broths ('OHNE Einlage'), pasta sauces/sugo, side dishes, cooking juice, sweets, gift boxes
NOT_MEAL_RE = re.compile(r"suppe$|sugo|pastaso(ß|ss)e|rotkraut|gulaschsaft|kekse|box|gutschein|geschenk", re.I)
SHIPPING = {"area": "Österreich und Deutschland", "free_from_eur_at": 100.0, "free_from_eur_de": 150.0, "fee_eur": 15.0,
            "source": BASE + "/ (Startseite 'Direkt zu DIR nach Hause')"}


def _txt(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>|</p>|</div>", "\n", s or "")
    return re.sub(r"[ \t\r\f\v]+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_sitemap(xml: str) -> list[dict]:
    seen, out = set(), []
    for m in PID_RE.finditer(xml):
        if m.group(2) in seen: continue
        seen.add(m.group(2)); out.append({"id": m.group(2), "url": m.group(1)})
    return out


def is_meal_name(name: str | None) -> bool:
    return bool(name) and not NOT_MEAL_RE.search(name.strip())


def _pick_images(media: list[dict]) -> tuple[str | None, str | None]:
    """(packshot, serving): packshot = first non-main picture on a homogeneous light background."""
    pack = serving = None
    for m in media or []:
        if m.get("type") != "PICTURE": continue
        u = m.get("image1500pxUrl") or m.get("image800pxUrl")
        b = (m.get("borderInfo") or {})
        light = not ((b.get("dominatingColor") or {}).get("isDark", True))
        if m.get("isMain"): serving = serving or u
        elif pack is None and b.get("homogeneity") and light: pack = u
    return pack, serving


def parse_product(d: dict, url: str | None = None) -> Product | None:
    if not d or not d.get("name"): return None
    o = d.get("defaultOptionsOverrides") or {}
    pr = o.get("pricesOverrides") or {}
    var = o.get("variationOverrides") or {}
    desc = _txt(d.get("description"))
    zut = re.search(r"Zutaten[^:\n]{0,12}:\s*(.+)", desc, re.S)
    zut = re.sub(r"\s+", " ", zut.group(1)).strip() if zut else None
    allerg = sorted(set(w for w in re.findall(r"\b[A-ZÄÖÜ]{4,}\b", zut or "")))
    units = " ".join(str(a.get("value") or "") for a in var.get("attributes") or [] if a.get("type") == "UNITS_IN_PRODUCT")
    vol = re.search(r"(\d+(?:[.,]\d+)?)\s*ml\b", units + " " + desc)
    pack, serving = _pick_images(var.get("mediaItems"))
    cats = [c["categoryPath"][-1]["name"] for c in d.get("categoryPaths") or [] if c.get("categoryPath")]
    pid = str((d.get("identifier") or {}).get("productId") or "")
    rib = (d.get("ribbon") or {}).get("text")
    name = d["name"].strip()
    vegan = True if re.search(r"vegan", name + " " + (rib or "") + " " + " ".join(cats), re.I) else None
    if url is None and (d.get("urls") or {}).get("directPageUrl"): url = BASE + d["urls"]["directPageUrl"]
    taxes = pr.get("appliedTaxes") or []
    return Product(source="ruckzuck", store=STORE, name=name, brand="Dunzinger's Ruck Zuck",
        price_eur=pr.get("basePriceWithModifiersDiscountAndTaxes"), unit="Stk", size_g=None, ean=None,
        image_url=pack, producer="Schimpl OG", origin="AT (Hirschbach im Mühlkreis, OÖ)", category="Fertiggerichte im Glas",
        source_url=url, source_id=pid or None,
        extra={"ingredients": zut, "allergens_marked": allerg or None, "volume_ml": float(vol.group(1).replace(",", ".")) if vol else None,
               "description": desc, "categories": cats, "ribbon": rib, "vegan": vegan,
               "sold_out": bool(var.get("isSoldOut")), "vat_percent": taxes[0].get("percent") if taxes else None,
               "lowest_30d": (pr.get("lowestPrice") or {}).get("labelForProductList"),
               "serving_image_url": serving, "image_kind": "jar packshot (printed dish label)" if pack else None,
               "storage": "ungekühlt haltbar (im Glas eingekocht, lt. Shop)",
               "nutrition_note": "ruckzuck-laden.at veröffentlicht keine Nährwerte/GTIN — nicht geschätzt",
               "price_basis": "Preis je Glas inkl. MwSt. lt. Ecwid-Storefront; Versand AT 15 € bzw. frei ab 100 €",
               "shipping": SHIPPING})


def product_json(pid: str | int, timeout: int = 40) -> dict | None:
    body = json.dumps({"productIdentifier": {"type": "PUBLISHED", "productId": int(pid)}}).encode()
    req = urllib.request.Request(API, data=body, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with polite_urlopen(req, timeout=timeout) as r: return json.loads(r.read())
    except Exception as e:
        if getattr(e, "code", None) in (400, 404, 410): return None
        raise


def product(url_or_id: str) -> Product | None:
    s = url_or_id.strip()
    m = re.search(r"-p(\d+)/?$", s) if s.startswith("http") else None
    pid = m.group(1) if m else s
    if not pid.isdigit(): return None
    return parse_product(product_json(pid), s if s.startswith("http") else None)


class RuckZuck(Adapter):
    id = "ruckzuck"; store = STORE; homepage = BASE; status = "live"
    notes = ("Live: ruckzuck-laden.at (Dunzinger's Ruck Zuck Glasl, Schimpl OG, Hirschbach im Mühlkreis OÖ; jar meals cooked "
             "in the jar, shelf-stable; ships AT (15 €, free from 100 €) and DE). WP sitemap → Ecwid public storefront JSON "
             "(robots allow; polite 1 req/s; no login/cart). Price incl. MwSt., ingredients, allergens, jar packshot. "
             "No GTIN/nutrition published.")
    def tiles(self) -> list[dict]:
        return parse_sitemap(get(SITEMAP, raw=True, timeout=40).decode("utf-8", "replace"))
    def _all(self) -> list[Product]:
        out = []
        for t in self.tiles():
            p = parse_product(product_json(t["id"]), t["url"])
            if p: out.append(p)
        return out
    def search(self, q: str, limit: int = 10) -> list[Product]:
        words = re.findall(r"\w{3,}", q.lower())
        return [p for p in self._all() if all(w in p.name.lower() for w in words)][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 60) -> list[Product]:
        ps = self._all()
        if category == "ready-meals": ps = [p for p in ps if is_meal_name(p.name)]
        return ps[:limit]
