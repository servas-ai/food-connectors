"""Fleischerei Buchberger (buchberger.shop) — Buchberger GmbH & Co KG, Mittelgasse 39, 8225 Pöllau (Steiermark;
FN 14170p, LG für ZRS Graz; UID ATU29190201, VIES valid 2026-10-25 'Buchberger GmbH & Co KG'): the butcher's own
webshop (JOLIOO platform) with an 'Essen im Glas' category of jar meals cooked in its kitchen in Pöllau.

Source (public server-rendered HTML, no login/cookies; robots.txt ``User-agent: *`` ``Allow: /``):
  * ``https://www.buchberger.shop/essen-im-glas`` — category listing (8 jars, 450 ml) → product URLs. One request.
  * ``https://www.buchberger.shop/<slug>`` — product page: title (h1), price 'X,XX EUR' per Stück, description with
    'Nährwerte für 100g: … kJ; … kcal; Eiweiß … g, Kohlenhydrate … g[. davon Zucker … g], Fett … g' (where printed),
    'Zutaten:'/'Zutatenliste:', 'Allergene:', 'MHD:' and storage line; images on public.jolioo.com. 1 req/s.
Ready meals = Gulasch-Suppe, Rindsgulasch, Hirschragout, Kalbsragout, Putencurry; excluded: Gulaschsaft, Sugo and
Sojabolognese (sauces). Nutrition is taken exactly as printed; several shop values fail an Atwater check (e.g.
Hirschragout 138 kcal vs ≈90 from the macros) and are flagged, never corrected. No GTIN published.
Shipping: shop footer 'Versandkostenfrei ab 120 € · Kühlversand'; delivery area and the fee below 120 € are not
published (AGB §6 refers to the shop) → shipping fee unknown, Austrian shop under Austrian law.
Photos: the product page's main image (single-jar packshot with the dish name on the label); vision gate 2026-10-25 5/5.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.buchberger.shop"
CATEGORY = f"{BASE}/essen-im-glas"
STORE = "Online: Fleischerei Buchberger"
PRODUCER = "Buchberger GmbH & Co KG, Mittelgasse 39, 8225 Pöllau, Steiermark (FN 14170p, LG für ZRS Graz; UID ATU29190201)"
SHIPPING_NOTE = ("Kühlversand; versandkostenfrei ab 120 € (Shop-Fußzeile); Liefergebiet und Versandkosten unter 120 € "
                 "nicht veröffentlicht (AGB §6 verweist auf den Shop)")
EXCLUDE = re.compile(r"gulaschsaft|sugo|bolognese", re.I)
PRODUCT_RE = re.compile(r'href="(https://www\.buchberger\.shop/buchberger-[a-z0-9-]*im-glas[a-z0-9-]*)"')


def _text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s or "", flags=re.S)
    s = _html.unescape(re.sub(r"<[^>]+>", "\n", s)).replace("\xa0", " ")
    return re.sub(r"\n\s*\n+", "\n", s)


def _num(s: str | None) -> float | None:
    return float(s.replace(",", ".")) if s else None


def category_urls(page: str | None = None) -> list[str]:
    page = page if page is not None else get(CATEGORY, headers={"Accept": "text/html"}, raw=True, timeout=30).decode("utf-8", "replace")
    return list(dict.fromkeys(PRODUCT_RE.findall(page)))


def is_meal(url_or_name: str) -> bool:
    return not EXCLUDE.search(url_or_name)


def parse(page: str, url: str) -> Product:
    t = _text(page)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    title = re.sub(r"\s+", " ", _html.unescape(h1.group(1))).strip() if h1 else url.rsplit("/", 1)[-1]
    name = re.sub(r"^BUCHBERGER\s+", "", title).strip()
    m = re.search(r"(\d+,\d{2})\s*EUR", t)
    price = _num(m.group(1)) if m else None
    ml = re.search(r"(\d+)\s*ML\b", title, re.I)
    size = float(ml.group(1)) if ml else None
    nut = {}
    n = re.search(r"Nährwerte für 100\s*g:\s*([^\n]+)", t)
    if n:
        line = n.group(1)
        for key, rx in (("energy_kj", r"(\d+(?:,\d+)?)\s*kJ"), ("energy_kcal", r"(\d+(?:,\d+)?)\s*kcal"),
                        ("protein_g", r"Eiweiß\s*(\d+(?:,\d+)?)"), ("carbs_g", r"Kohlenhydrate\s*(\d+(?:,\d+)?)"),
                        ("sugar_g", r"Zucker\s*(\d+(?:,\d+)?)"), ("fat_g", r"Fett\s*(\d+(?:,\d+)?)")):
            v = re.search(rx, line)
            if v: nut[key] = _num(v.group(1))
    ing = re.search(r"Zutaten(?:liste)?:\s*([^\n]+)", t)
    alg = re.search(r"Allergene:\s*([^\n]+)", t)
    mhd = re.search(r"MHD:\s*([^\n]+)", t)
    sto = re.search(r"(Im Kühlschrank[^\n]+)", t)
    img = re.search(r'src="(https://public\.jolioo\.com/generated/h1000w1000m1/[^"]+\.(?:jpg|png|webp))"', page)
    atw = None
    if all(k in nut for k in ("energy_kcal", "protein_g", "carbs_g", "fat_g")):
        calc = 4 * nut["protein_g"] + 4 * nut["carbs_g"] + 9 * nut["fat_g"]
        atw = {"calc_kcal": round(calc, 1), "ok": abs(calc - nut["energy_kcal"]) <= max(15, 0.15 * nut["energy_kcal"])}
    low = name.lower()
    return Product(
        source="buchberger", store=STORE, name=name.title().replace("Im Glas", "im Glas").replace(" Ml", " ml"),
        brand="Buchberger", price_eur=price,
        unit_price_eur=round(price / size * 100, 2) if price and size else None,
        unit="100 ml" if price and size else None, size_g=size, nutrition_100g=nut, ean=None,
        image_url=img.group(1) if img else None, producer=PRODUCER,
        origin="AT (gekocht in der Buchberger-Küche Pöllau, Steiermark lt. Shop)",
        category="Suppe" if "suppe" in low else "Fertiggericht", source_url=url, source_id=url.rsplit("/", 1)[-1],
        extra={"title": title, "pack": "Glas 450 ml", "ingredients": ing.group(1).strip() if ing else None,
               "allergens": alg.group(1).strip() if alg else None, "mhd": mhd.group(1).strip() if mhd else None,
               "storage": sto.group(1).strip() if sto else None, "atwater": atw,
               "price_note": "Preis je Glas (Stück) inkl. MwSt. lt. Produktseite; Größe = 450 ml lt. Titel",
               "shipping_note": SHIPPING_NOTE},
    )


def product(slug_or_url: str, page_html: str | None = None) -> Product | None:
    k = slug_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    url = f"{BASE}/{k}"
    if page_html is None:
        if url not in category_urls():
            return None
        page_html = get(url, headers={"Accept": "text/html"}, raw=True, timeout=30).decode("utf-8", "replace")
    return parse(page_html, url)


class Buchberger(Adapter):
    id = "buchberger"
    store = STORE
    homepage = BASE
    notes = ("Live: Fleischerei Buchberger webshop (Buchberger GmbH & Co KG, Pöllau, Steiermark): 'Essen im Glas' jar "
             "meals 450 ml (Gulasch-Suppe, Rindsgulasch, Hirsch-/Kalbsragout, Putencurry) with price, €/100 ml, "
             "ingredients/allergens, nutrition as printed, MHD, photo; sauces excluded; Kühlversand, free from 120 €")

    def fetch(self, category="ready-meals", limit=50):
        return [product(u) for u in category_urls() if is_meal(u)][:limit]

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        return [p for p in self.fetch() if p and all(w in (p.name + " " + (p.extra.get("ingredients") or "")).lower() for w in words)][:limit]
