"""Fleischhauerei Gerbl (Vöcklamarkt/Timelkam, OÖ) — live connector for the 'Gerbl im Glas' ready meals.

Shop: shop.gerbl.at (Fleischhauerei Gerbl GmbH, Hauptstraße 14, 4870 Vöcklamarkt; FN 612319w LG Wels,
UID ATU79858539 per /gerbl-shop/shop/info/impressum, VIES valid). Shipping per /gerbl-shop/shop/info/versandkosten:
within Austria only (so Linz is inside), flat 9,90 € packaging + EMS express; dispatch every Tuesday, 1–2 working days.
Jars are pasteurised ('haltbar gemacht durch Erhitzen'), stored chilled 2–6 °C, approx. 12 weeks unopened;
empty jars are taken back.

Access path (no login, no cookies, no JS):
  category https://shop.gerbl.at/ecommerce/category-browse?category_id=150129  ('Gerbl im Glas', product links)
  product  https://shop.gerbl.at/ecommerce/product?product_id=<id>&category_id=150129
           (h1, one-line description '…, 450 ml.', data-price brutto, Zutaten, Allergene, Haltbarkeit,
            Verpackungsgröße, main photo /gallery-file/…/picture-orig.jpg)
robots.txt (checked 2026-10-18): ``User-agent: *`` disallows only /ftpdir/, /admin/, /ecommerce/dc_components/
(never used). Cart / register endpoints are never called. Requests go through the food-connectors polite gate.
The shop publishes NO GTIN and NO nutrition table → those fields stay empty (never estimated). Pack size is given
as jar volume in ml ('ca. 450 ml') → size_g stays empty, the volume is kept in extra.volume_ml.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://shop.gerbl.at"
CATEGORY_ID = "150129"
CATEGORY = BASE + "/ecommerce/category-browse?category_id=" + CATEGORY_ID
STORE = "Online: Gerbl im Glas"
LINK_RE = re.compile(r'href="(/ecommerce/product\?product_id=(\d+)&(?:amp;)?category_id=%s)"' % CATEGORY_ID)
# some products use a vanity slug instead (e.g. '/rindsgulasch'); taken from the product-name link of a tile
SLUG_RE = re.compile(r'<div class="product-name">\s*<a href="(/[a-z0-9-]+)">')
NOT_MEAL_RE = re.compile(r"geschenk|korb|streichwurst|leber|aufstrich|gutschein", re.I)


def _txt(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>|</p>", "\n", s or "")
    return re.sub(r"[ \t\r\f\v]+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_category(h: str) -> list[dict]:
    """Product ids + URLs from the 'Gerbl im Glas' category page (order kept, deduplicated)."""
    seen, out = set(), []
    for m in LINK_RE.finditer(h):
        pid = m.group(2)
        if pid in seen: continue
        seen.add(pid)
        out.append({"id": pid, "url": BASE + _html.unescape(m.group(1))})
    for m in SLUG_RE.finditer(h):
        slug = m.group(1)
        if slug in seen: continue
        seen.add(slug)
        out.append({"id": slug.strip("/"), "url": BASE + slug})
    return out


def _section(h: str, title: str) -> str | None:
    m = re.search(r"<h3>%s</h3>\s*<p>(.*?)</p>" % title, h, re.S)
    return _txt(m.group(1)) if m else None


def is_meal_name(name: str | None) -> bool:
    return bool(name) and not NOT_MEAL_RE.search(name)


def parse_product(h: str, url: str) -> Product | None:
    m = re.search(r'<div class="row ecommerce" id="product">.*?<h1>(.*?)</h1>', h, re.S)
    if not m: return None
    full = _txt(m.group(1))
    code = re.search(r"\((GIG\s*\d+)\)", full)
    name = re.sub(r"\s*\(GIG\s*\d+\)\s*", " ", full).strip()
    name = re.sub(r"\s+VEGETARISCH\b", "", name).strip()
    pid = re.search(r'name="product_id" value="(\d+)"', h)
    price = re.search(r'<div data-price="([\d.]+)" class="add-to-cart">', h)
    one = re.search(r'<div class="product-one-line-description">(.*?)</div>', h, re.S)
    img = re.search(r'id="product-pic-div">.*?href="(/gallery-file/[^"]+/picture-orig\.jpg)"', h, re.S)
    pack = _section(h, "Verpackungsgr&ouml;&szlig;e") or _section(h, "Verpackungsgröße")
    vol_src = " ".join(x for x in [pack, _txt(one.group(1)) if one else None] if x)
    vol = re.search(r"(\d+(?:[.,]\d+)?)\s*ml\b", vol_src)
    zut = _section(h, "Zutaten")
    allerg = _section(h, "Allergene")
    shelf = _section(h, "Haltbarkeit")
    veg = True if re.search(r"VEGETARISCH", full) else None
    return Product(source="gerbl", store=STORE, name=name, brand="Gerbl",
        price_eur=float(price.group(1)) if price else None, unit="Stk", size_g=None, ean=None,
        image_url=BASE + img.group(1) if img else None,
        producer="Fleischhauerei Gerbl GmbH", category="Gerbl im Glas", source_url=url,
        source_id=pid.group(1) if pid else None,
        extra={"article_code": re.sub(r"\s+", "", code.group(1)) if code else None,
               "volume_ml": float(vol.group(1).replace(",", ".")) if vol else None,
               "pack_text": pack, "ingredients": zut, "allergens": allerg, "shelf_life": shelf,
               "storage": "gekühlt 2–6 °C (pasteurisiertes Glas)" if shelf and re.search(r"gek(ü|&uuml;)hlt", shelf, re.I) else None,
               "vegetarian": veg, "jar_return": "Gläser nehmen wir gerne zurück" in _html.unescape(h) or None,
               "nutrition_note": "shop.gerbl.at veröffentlicht keine Nährwerte/EAN — nicht geschätzt",
               "size_note": "nur Glasvolumen in ml angegeben → size_g leer",
               "price_basis": "Preis je Stück/Glas inkl. MwSt. lt. Produktseite, zzgl. 9,90 € Verpackung+Versand (EMS) innerhalb Österreichs",
               "delivery_area": "ganz Österreich (Versand jeden Dienstag, 1–2 Werktage)"})


def product(url_or_id: str) -> Product | None:
    s = url_or_id.strip()
    if not s.startswith("http"):
        s = f"{BASE}/ecommerce/product?product_id={s}&category_id={CATEGORY_ID}"
    try: h = get(s, raw=True, timeout=40).decode("utf-8", "replace")
    except Exception as e:
        if getattr(e, "code", None) in (404, 410): return None
        raise
    return parse_product(h, s)


class Gerbl(Adapter):
    id = "gerbl"; store = STORE; homepage = BASE; status = "live"
    notes = ("Live: shop.gerbl.at 'Gerbl im Glas' (Fleischhauerei Gerbl GmbH, Vöcklamarkt OÖ; pasteurised glass-jar "
             "meals, shipped within Austria incl. Linz for 9,90 € EMS). Category page + product pages (robots allow; "
             "polite 1 req/s; no login/cart). Price, volume (ml), ingredients, allergens, shelf life, official photo. "
             "No GTIN/nutrition published.")
    def tiles(self) -> list[dict]:
        return parse_category(get(CATEGORY, raw=True, timeout=40).decode("utf-8", "replace"))
    def _all(self) -> list[Product]:
        out = []
        for t in self.tiles():
            p = parse_product(get(t["url"], raw=True, timeout=40).decode("utf-8", "replace"), t["url"])
            if p: out.append(p)
        return out
    def search(self, q: str, limit: int = 10) -> list[Product]:
        words = [w for w in re.findall(r"\w{3,}", q.lower())]
        return [p for p in self._all() if all(w in p.name.lower() for w in words)][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 60) -> list[Product]:
        ps = self._all()
        if category == "ready-meals": ps = [p for p in ps if is_meal_name(p.name)]
        return ps[:limit]
