"""Land-Fleischerei Fichtenbauer (fleischerei-fichtenbauer.at) — Land-Fleischerei Fichtenbauer GmbH, Firmensitz
Hauptstraße 12, 3872 Amaliendorf; shop Stadtplatz 33, 3950 Gmünd (Waldviertel, NÖ; FN 523618b, LG Krems an der Donau;
UID ATU74965969, VIES valid 2026-10-25 'Landfleischerei Fichtenbauer GmbH', Hauptstraße 12, AT-3872 Amaliendorf;
GLEIF fulltext 'Fichtenbauer' → 0 records, no LEI): the butcher's own Contao webshop with a few 'essfertig' jar meals.

Source (public server-rendered HTML, no login/cookies; robots.txt disallows only /contao/ and /_contao/):
  * ``https://www.fleischerei-fichtenbauer.at/shop`` — shop listing (21 products) → ``shop/<slug>`` links. One request.
  * ``https://www.fleischerei-fichtenbauer.at/shop/<slug>`` — product page with schema.org microdata (itemprop name,
    sku = pack text 'im 400g Glas', description incl. 'Zutaten: …', Offer price) + base price '€ / 100 g' + packshot.
The site runs a request-rate verification page ('Please wait while your request is being verified', 12 KB HTML with a
5 s JS reload). It is never solved or scripted around: requests are spaced 3 s apart; if the page still appears the
adapter waits 10 s once, re-requests like a normal reload, and otherwise skips the product (returns None).
Ready meals = jar dishes 'im …g Glas': Rindsgulasch, Beuschel, Wildragout (400 g). Excluded: Bolognese Sauce (sauce),
smoked cold cuts sold 'essfertig' (Bauchfleisch, Karreeroller, Zigeunerspeck), sausages, salami, pâtés.
No nutrition and no GTIN published → never estimated. Ingredients as printed on the product page.
Shipping (versand-zahlung): 10 € flat, free from 99 €; AGB: 'Der Webshop ist auf Österreich ausgerichtet' (AT incl. Linz).
Photos: product packshot (800x600 jpg, jar with dish-name lid label); vision gate 2026-10-25 3/3.
"""
from __future__ import annotations
import html as _html, re, time
from urllib.parse import unquote
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.fleischerei-fichtenbauer.at"
SHOP = f"{BASE}/shop"
STORE = "Online: Fleischerei Fichtenbauer"
PRODUCER = ("Land-Fleischerei Fichtenbauer GmbH, Hauptstraße 12, 3872 Amaliendorf / Stadtplatz 33, 3950 Gmünd, "
            "Niederösterreich (FN 523618b, LG Krems an der Donau; UID ATU74965969)")
SHIPPING_EUR = 10.0
SHIPPING_NOTE = ("Webshop auf Österreich ausgerichtet (AGB); Versand-Pauschale 10 € unter 99 €, ab 99 € versandkostenfrei "
                 "(Versand & Zahlung); Zahlung online (Kreditkarte, Apple/Google Pay, eps)")
EXCLUDE = re.compile(r"bolognese|sauce|speck|bauchfleisch|karreeroller|salami|w[uü]rstel|pastete|maisen|blutwurst|trommel", re.I)
CHALLENGE = "being verified"
DELAY_S = 3.0


def _fetch(url: str) -> str | None:
    for wait in (0, 10):
        if wait:
            time.sleep(wait)
        page = get(url, headers={"Accept": "text/html"}, raw=True, timeout=30).decode("utf-8", "replace")
        if CHALLENGE not in page:
            return page
    return None


def shop_urls(page: str | None = None) -> list[str]:
    page = page if page is not None else _fetch(SHOP) or ""
    return list(dict.fromkeys(f"{BASE}/shop/{s}" for s in re.findall(r'href="shop/([^"/?#]+)"', page)))


def is_meal(url_or_name: str) -> bool:
    s = unquote(url_or_name)
    return "essfertig" in s.lower() and not EXCLUDE.search(s)


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def parse(page: str, url: str) -> Product | None:
    nm = re.search(r'itemprop="name">([^<]+)<', page)
    pr = re.search(r'itemprop="price" content="([\d.]+)"', page)
    if not nm or not pr:
        return None
    name = _html.unescape(nm.group(1)).strip()
    pack = re.search(r'itemprop="sku">([^<]+)<', page)
    pack = _html.unescape(pack.group(1)).strip() if pack else ""
    if "glas" not in pack.lower():
        return None  # only jar dishes are ready meals here
    g = re.search(r"(\d+)\s*g", pack)
    size = float(g.group(1)) if g else None
    price = float(pr.group(1))
    bp = re.search(r'class="baseprice">.*?([\d,]+)\s*/\s*100\s*g', page, re.S)
    zu = re.search(r"Zutaten:\s*([^<]+)<", page)
    img = re.search(r'<img src="(assets/images/[^"]+\.jpe?g)"', page)
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    return Product(
        source="fichtenbauer", store=STORE, name=name, brand="Fichtenbauer", price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if size else None, unit="kg" if size else None,
        size_g=size, nutrition_100g={}, ean=None, image_url=f"{BASE}/{img.group(1)}" if img else None, producer=PRODUCER,
        origin="AT (hergestellt in der Land-Fleischerei Fichtenbauer, Waldviertel lt. Shop)",
        category="Fertiggericht", source_url=url, source_id=unquote(slug),
        extra={"pack": pack, "ingredients": _html.unescape(zu.group(1)).strip() if zu else None,
               "unit_price_eur_100g_shop": _num(bp.group(1)) if bp else None,
               "price_note": "Preis je Glas inkl. MwSt. lt. Produktseite (schema.org Offer)", "shipping_note": SHIPPING_NOTE},
    )


def product(slug_or_url: str, page_html: str | None = None) -> Product | None:
    k = slug_or_url.strip().rstrip("/").split("/")[-1].split("?")[0]
    url = f"{SHOP}/{k}"
    if page_html is None:
        page_html = _fetch(url)
        if page_html is None:
            return None
    return parse(page_html, url)


class Fichtenbauer(Adapter):
    id = "fichtenbauer"
    store = STORE
    homepage = BASE
    notes = ("Live: Land-Fleischerei Fichtenbauer webshop (Gmünd/Amaliendorf, Waldviertel NÖ): 'essfertig' jar meals "
             "(Rindsgulasch, Beuschel, Wildragout 400 g) with price, €/kg, ingredients, photo; sauce and smoked cold cuts "
             "excluded; AT shipping 10 €, free from 99 €")

    def fetch(self, category="ready-meals", limit=50):
        out = []
        for u in [u for u in shop_urls() if is_meal(u)][:limit]:
            time.sleep(DELAY_S)
            p = product(u)
            if p:
                out.append(p)
        return out

    def search(self, q, limit=20):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        return [p for p in self.fetch() if all(w in (p.name + " " + (p.extra.get("ingredients") or "")).lower() for w in words)][:limit]
