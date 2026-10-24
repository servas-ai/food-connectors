"""voeslauermanufaktur (voeslauermanufaktur.at) — small Bad Vöslau (NÖ) kitchen of Isabella Schnabel selling its own
pasteurised, preservative-free heat-up jar meals and soups ('Feinkost im Glas') in a Jimdo webshop, delivered in AT.

Source (public, no login/cookies; robots.txt ``User-agent: *`` disallows /app/ and /j/ (allows
/app/module/webproduct/goto/), ``Crawl-Delay: 5`` → we sleep 5 s between the two page requests):
  * server-rendered category pages ``/shop/feinkost-im-glas/hauptgerichte/`` and ``/shop/feinkost-im-glas/suppen/``
    with schema.org Product microdata per product module (name, description, price incl. MwSt., availability,
    product image) followed by a text module with 'Zutaten: …' and 'Inhalt: N g' (and a 'vegan' badge).
Ready meals = all Hauptgerichte + Suppen minus the clear broth 'Echtes Rindssupperl' (without Einlage).
Sides from 'Gemüse essfertig' (Letscho, Sauerkraut, gegrillte Tomaten), Sugo, Pesto, Antipasti are not meals.
No nutrition table and no GTIN are published → never estimated.
Shipping (AGB §4.6/§6, read 2026-10-24): delivery to the order address in Austria, 7 working days (shop badge
'3 - 5 Tage Lieferzeit'); free delivery within Austria from 180 €, below that the fee is shown only in the checkout
(the Jimdo delivery-info page lives under /j/ = robots-disallowed, not read).
Operator (Impressum/AGB §3): voeslauermanufaktur, Inh. Isabella Schnabel, Einzelunternehmen/Kleinunternehmen,
Flugfeldstraße 4, 2540 Bad Vöslau, WKNÖ member, Gewerbebehörde BH Baden; no Firmenbuch entry and no UID published
(Kleinunternehmer) → not VIES-verifiable.
Photos: Jimdo product main images; vision gate 2026-10-24 11/12 PASS (mit-Speck soup reuses the plain soup photo → dropped;
the Rindssupperl mit Fleischeinlage has no photo).
"""
from __future__ import annotations
import html as _html, re, time
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.voeslauermanufaktur.at"
STORE = "Online: voeslauermanufaktur"
PRODUCER = "voeslauermanufaktur, Inh. Isabella Schnabel (Einzelunternehmen), Flugfeldstraße 4, 2540 Bad Vöslau (kein FN, keine UID veröffentlicht)"
SHIPPING_EUR = None  # only in checkout (/j/ robots-disallowed); free in AT from 180 €
SHIPPING_NOTE = ("Lieferung an die Bestelladresse in Österreich (AGB §6: 7 Werktage; Shop: 3–5 Tage), "
                 "versandkostenfrei innerhalb Österreichs ab 180 € (AGB §4.6), darunter Versandkosten erst im Warenkorb")
STORAGE = "Glas, durch Pasteurisation haltbar gemacht, ohne Konservierungsstoffe (Lagerhinweis nicht angegeben)"
PAGES = {"Hauptgericht": "/shop/feinkost-im-glas/hauptgerichte/", "Suppe": "/shop/feinkost-im-glas/suppen/"}
CRAWL_DELAY = 5
# vision gate 2026-10-24: 'Erdäpfelcremesuppe mit Speck' reuses the byte-identical photo of the plain Erdäpfelcremesuppe
BAD_PHOTO = {"mbd085715cb6d6dd5"}
EXCLUDE = re.compile(r"^echtes rindssupperl$", re.I)  # clear broth; the 'mit Fleischeinlage' variant stays


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def parse_page(html: str, line: str) -> list[dict]:
    """Split a Jimdo shop page into product modules; attach the following text module (Zutaten/Inhalt/vegan)."""
    parts = re.split(r'<div id="cc-m-\d+" class="j-module n j-product ">', html)[1:]
    out = []
    for p in parts:
        name = re.search(r'<h4 class="fn" itemprop="name">(.*?)</h4>', p, re.S)
        if not name:
            continue
        price = re.search(r'itemprop="price" content="([\d.]+)"', p)
        avail = re.search(r'itemprop="availability" content="(\w+)"', p)
        goto = re.search(r'itemprop="url" content="[^"]*/goto/m/(\w+)"', p)
        img = re.search(r'class="cc-product-superzoom[^"]*" rel="lightbox" data-href="([^"]+)"', p) or \
            re.search(r'class="cc-shop-product-main-image photo"[^>]*src="([^"]+)"', p)
        desc = re.search(r'itemprop="description">(.*?)</div>', p, re.S)
        tail = p.split("<!-- end of div.hproduct -->", 1)[-1]
        txt = _clean(tail.split('class="j-module n j-product', 1)[0])
        ingr = re.search(r"Zutaten:\s*(.*?)(?:\s*Inhalt:|$)", txt)
        size = re.search(r"Inhalt:\s*([\d.,]+)\s*g\b", txt)
        out.append({"name": _clean(name.group(1)), "line": line,
                    "price": float(price.group(1)) if price else None,
                    "in_stock": (avail.group(1) == "InStock") if avail else None,
                    "id": goto.group(1) if goto else None,
                    "image": img.group(1) if img else None,
                    "description": _clean(desc.group(1)) if desc else None,
                    "ingredients": ingr.group(1).strip(" ,") if ingr else None,
                    "size_g": float(size.group(1).replace(",", ".")) if size else None,
                    "vegan": bool(re.search(r"Inhalt:\s*[\d.,]+\s*g\s+vegan\b", txt, re.I)),
                    "page": BASE + PAGES[line]})
    return out


def store_products() -> list[dict]:
    out = []
    for i, (line, path) in enumerate(PAGES.items()):
        if i:
            time.sleep(CRAWL_DELAY)
        out += parse_page(get(BASE + path, raw=True, timeout=40).decode("utf-8", "replace"), line)
    return out


def is_meal(sp: dict) -> bool:
    return bool(sp.get("name")) and not EXCLUDE.search(sp["name"].strip())


def to_product(sp: dict) -> Product:
    price, size = sp.get("price"), sp.get("size_g")
    ingr = sp.get("ingredients") or ""
    return Product(
        source="voeslauermanufaktur",
        store=STORE,
        name=sp["name"],
        brand="voeslauermanufaktur",
        price_eur=price,
        unit_price_eur=round(price / size * 100, 2) if price and size else None,
        unit="100 g" if price and size else None,
        size_g=size,
        nutrition_100g={},
        ean=None,
        image_url=None if sp.get("id") in BAD_PHOTO else sp.get("image"),
        producer=PRODUCER,
        category="Fertiggericht",
        source_url=sp["page"],
        source_id=sp.get("id"),
        extra={
            "jimdo_id": sp.get("id"),
            "line": sp["line"],
            "in_stock": sp.get("in_stock"),
            "vegan": sp.get("vegan", False),
            "vegetarian": sp.get("vegan", False),  # only the shop's vegan badge; no vegetarian label published
            "bio_claim": bool(re.search(r"\bBio\b", sp["name"])),
            "description": sp.get("description"),
            "ingredients": ingr or None,
            "storage": STORAGE,
            "price_note": "Preis je Glas inkl. MwSt. lt. schema.org-Microdata der Shopseite; €/100 g berechnet aus 'Inhalt'",
            "shipping_note": SHIPPING_NOTE,
        },
    )


def product(id_or_name: str, shop: list[dict] | None = None) -> Product | None:
    k = id_or_name.strip().rstrip("/").split("/")[-1].lower()
    sp = next((p for p in (shop if shop is not None else store_products())
               if (p.get("id") or "").lower() == k or p["name"].lower() == k), None)
    return to_product(sp) if sp else None


class Voeslauermanufaktur(Adapter):
    id = "voeslauermanufaktur"
    store = STORE
    homepage = BASE
    notes = ("Live: server-rendered Jimdo shop pages Hauptgerichte + Suppen of voeslauermanufaktur (Isabella Schnabel, "
             "Bad Vöslau): pasteurised heat-up jar meals and soups 345–430 g, price incl. MwSt., availability, "
             "ingredients, vegan badge, photos; AT delivery, free from 180 €; no nutrition/GTIN; 2 requests, 5 s crawl-delay")

    def fetch(self, category="ready-meals", limit=500):
        return [to_product(sp) for sp in store_products() if is_meal(sp)][:limit]

    def search(self, q, limit=50):
        words = [w.lower() for w in re.findall(r"\w{3,}", q)]
        out = []
        for sp in store_products():
            if not is_meal(sp):
                continue
            hay = (sp["name"] + " " + (sp.get("description") or "") + " " + (sp.get("ingredients") or "")).lower()
            if all(w in hay for w in words):
                out.append(to_product(sp))
        return out[:limit]
