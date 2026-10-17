"""Biohof Achleitner (Eferding, OÖ) — live connector for the 'Hausg'mocht' ready meals of the Bio-Kulinarium Achleitner.

Shop: www.biohof.at (Biokiste delivery service of Achleitner Biohof GmbH, Unterm Regenbogen 1, 4070 Eferding;
FN 154057f LG Wels, UID ATU41942706 per /impressum). Delivery area per /registrieren: Oberösterreich, Salzburg,
Steiermark, western Niederösterreich and some areas along the German border (so Linz is inside); Biokiste orders
(min. 23 €) are delivered free, other orders free from 30 € else 4,50 € (/versandkosten). Glass jars are Mehrweg
(returned with the next Biokiste).

Access path (no login, no cookies, no JS):
  category https://www.biohof.at/hausgmocht-speisen  (server-rendered tiles: data-name, data-price, data-hersteller,
           data-kennzeichen labels, artikelID, thumbnail, 'In den Warenkorb' = orderable this delivery week)
  product  https://www.biohof.at/<Slug>-<artikelID>    (h1, Produktinformation (Füllmenge, Zubereitung), Zutaten,
           price incl. MwSt., og:image 520 px)
robots.txt (checked 2026-10-17): ``User-agent: *`` Allow: / — disallows only /inc/, /templates/, /components/,
/print.cfm (never used). The PLZ check / registration / cart endpoints are never called. Requests go through the
food-connectors polite gate (robots.txt enforced, ≥1 s per host).
biohof.at publishes NO GTIN and NO nutrition table for these jars → those fields stay empty (never estimated).
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product, parse_size_g

BASE = "https://www.biohof.at"
CATEGORY = BASE + "/hausgmocht-speisen"
STORE = "Online: Biohof Achleitner"
TILE_RE = re.compile(r'<div class="entry[^"]*"(?P<attrs>[^>]*)>(?P<body>.*?)(?=<div class="entry |<footer|$)', re.S)
NOT_MEAL_RE = re.compile(r"fruchtaufstrich|klare|sirup|kuchen|apfelmus|sugo|bolognese|\blax\b|paket|marmelade|pesto|aufstrich", re.I)
MEAL_RE = re.compile(r"eintopf|gulasch|curry|suppe|knödel|moussaka|ragout|rindssuppe|lasagne|chili|risotto|gröstl|strudel", re.I)

def _txt(s: str | None) -> str:
    s = re.sub(r"<br\s*/?>|</p>", "\n", s or "")
    return re.sub(r"[ \t\r\f\v]+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def _attr(attrs: str, k: str) -> str | None:
    m = re.search(r'data-%s="([^"]*)"' % k, attrs)
    return _html.unescape(m.group(1)).strip() if m else None

def parse_category(h: str) -> list[dict]:
    """Tiles of a biohof.at category page → list of dicts (id, name, price, producer, labels, url, thumb, orderable)."""
    out = []
    for m in TILE_RE.finditer(h):
        a, b = m.group("attrs"), m.group("body")
        aid = re.search(r'data-artikelID="(\d+)"', b)
        href = re.search(r'<h3><a href="(/[^"]+)"', b)
        if not (aid and href): continue
        img = re.search(r'<img src="(/uploadPim/[^"]+)"', b)
        price = _attr(a, "price")
        out.append({"id": aid.group(1), "name": _attr(a, "name"), "price_eur": float(price) if price else None,
                    "producer": _attr(a, "hersteller"), "labels": [x for x in (_attr(a, "kennzeichen") or "").split(",") if x.strip()],
                    "url": BASE + href.group(1), "thumb": BASE + img.group(1) if img else None,
                    "orderable": "In den Warenkorb" in b})
    return out

def is_meal_name(name: str | None) -> bool:
    n = name or ""
    return bool(MEAL_RE.search(n)) and not NOT_MEAL_RE.search(n)

def _section(h: str, title: str) -> str | None:
    m = re.search(r"<h2>%s</h2>\s*<div class=\"infobox\">(.*?)</div>" % re.escape(title), h, re.S)
    return _txt(m.group(1)) if m else None

def parse_product(h: str, url: str, tile: dict | None = None) -> Product | None:
    m = re.search(r"<h1>(.*?)</h1>", h, re.S)
    if not m: return None
    name = _txt(m.group(1))
    aid = re.search(r'class="[^"]*productDetail" data-artikelID="(\d+)"', h)
    price = re.search(r'<div class="price">\s*<strong>€\s*([\d.,]+)', h)
    og = re.search(r'<meta property="og:image" content="([^"]+)"', h)
    desc = re.search(r'<meta property="og:description" content="([^"]*)"', h)
    info = _section(h, "Produktinformation") or ""
    zut = _section(h, "Inhaltsstoffe / Zutaten")
    fill = re.search(r"Füllmenge:\s*([^|\n]+)", info)
    size_txt = fill.group(1).strip() if fill else None
    # 'ca. 350ml in einem 410ml Glas' → content (first quantity), never the jar volume
    size, size_note = None, None
    if size_txt and re.search(r"\bin einem\b", size_txt):
        size = parse_size_g(re.split(r"\bin einem\b", size_txt)[0])
    elif size_txt and re.search(r"glas", size_txt, re.I):
        size_note = "nur Glasvolumen angegeben (Inhalt nicht genannt) → size_g leer"  # '410ml Glas' = jar, not content
    elif size_txt:
        size = parse_size_g(size_txt)
    if size is None and not size_note:
        mm = re.search(r"(\d+(?:[.,]\d+)?)\s*(g|kg)\b", name)  # e.g. 'Linsen Moussaka 400g'
        if mm: size, size_note = parse_size_g(mm.group(0)), "Menge aus dem Produktnamen"
    prep = re.search(r"Zubereitung:\s*([^|\n]+)", info)
    labels = (tile or {}).get("labels") or re.findall(r'/images/tags/([A-Za-z]+)\.png', h)
    p_eur = float(price.group(1).replace(".", "").replace(",", ".")) if price else (tile or {}).get("price_eur")
    sub = re.search(r'<div class="subhdr"><a[^>]*>(.*?)</a>', h, re.S)
    producer = _txt(sub.group(1)) if sub else (tile or {}).get("producer")
    return Product(source="biohof-achleitner", store=STORE, name=name, brand="Biohof Achleitner",
        price_eur=p_eur, unit="Stk", size_g=size, ean=None, image_url=og.group(1) if og else (tile or {}).get("thumb"),
        producer=producer, category="Hausg'mocht Speisen", source_url=url,
        source_id=aid.group(1) if aid else (tile or {}).get("id"),
        extra={"fill_text": size_txt, "preparation": prep.group(1).strip() if prep else None,
               "ingredients": zut, "description": _html.unescape(desc.group(1)).strip() if desc else None,
               "labels": labels, "mehrweg": any(l.lower() == "mehrweg" for l in labels) or "Mehrwegglas" in info,
               "vegan": any(l.lower() == "vegan" for l in labels), "bio": True if zut and re.search(r"kontrolliert biologisch", zut) else None,
               "size_note": size_note,
               "available_window": (re.search(r"Verfügbar vom ([\d.]+\s*-\s*[\d.]+)", _html.unescape(desc.group(1))) or [None, None])[1] if desc else None,
               "orderable_this_week": (tile or {}).get("orderable"),
               "nutrition_note": "biohof.at veröffentlicht keine Nährwerte/EAN — nicht geschätzt",
               "price_basis": "Preis je Stück/Glas inkl. MwSt. lt. biohof.at Produktseite, zzgl. Versand (Biokiste ab 23 € frei Haus; sonst ab 30 € frei, darunter 4,50 €)",
               "delivery_area": "OÖ, Salzburg, Steiermark, westliches NÖ, Teile entlang der deutschen Grenze (biohof.at/registrieren)"})

def product(url_or_id: str) -> Product | None:
    s = url_or_id.strip()
    tile = None
    if not s.startswith("http"):
        tile = next((t for t in parse_category(get(CATEGORY, raw=True, timeout=40).decode("utf-8", "replace")) if t["id"] == s), None)
        if not tile: return None
        s = tile["url"]
    try: h = get(s, raw=True, timeout=40).decode("utf-8", "replace")
    except Exception as e:
        if getattr(e, "code", None) in (404, 410): return None
        raise
    return parse_product(h, s, tile)

class BiohofAchleitner(Adapter):
    id = "biohof-achleitner"; store = STORE; homepage = BASE; status = "live"
    notes = ("Live: biohof.at 'Hausg'mocht Speisen' (Bio-Kulinarium Achleitner, Eferding; Mehrweg glass jars, delivered "
             "with the Biokiste in OÖ incl. Linz, Salzburg, Steiermark, west NÖ). Category tiles + product pages (robots "
             "Allow: /; polite 1 req/s; no login/cart/PLZ endpoints). Price, Füllmenge, Zubereitung, Zutaten, labels, "
             "orderable flag, official photo. No GTIN/nutrition published.")
    def tiles(self) -> list[dict]:
        return parse_category(get(CATEGORY, raw=True, timeout=40).decode("utf-8", "replace"))
    def search(self, q: str, limit: int = 10) -> list[Product]:
        words = [w for w in re.findall(r"\w{3,}", q.lower())]
        ts = [t for t in self.tiles() if all(w in (t["name"] or "").lower() for w in words)][:limit]
        return [p for p in (parse_product(get(t["url"], raw=True, timeout=40).decode("utf-8", "replace"), t["url"], t) for t in ts) if p]
    def fetch(self, category: str = "ready-meals", limit: int = 60) -> list[Product]:
        ts = self.tiles()
        if category == "ready-meals": ts = [t for t in ts if is_meal_name(t["name"])]
        out = []
        for t in ts[:limit]:
            p = parse_product(get(t["url"], raw=True, timeout=40).decode("utf-8", "replace"), t["url"], t)
            if p: out.append(p)
        return out
