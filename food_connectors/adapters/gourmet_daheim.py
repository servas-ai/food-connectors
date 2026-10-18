"""GOURMET Daheim (GMS Gourmet GmbH, Wien) via its Upper-Austria partner Mahlzeit Vertriebs GmbH (Linz) —
live connector for the frozen à-la-carte ready meals ("Tiefkühlmenüs à la carte", Essen auf Rädern).

Mahlzeit Vertriebsges.m.b.H., Melissenweg 34, 4020 Linz delivers the GOURMET Daheim frozen menus once a week to
private households all over Upper Austria (incl. Linz); minimum order = 1 carton of 7 main dishes, delivery free
with at least one main-dish carton, no contract (mahlzeit.co.at/a-la-carte/).

Access path (official public PDFs, no login, no cookies, no JS):
  prices     https://www.mahlzeit.co.at/wp-content/uploads/2026/03/Preisliste_Bestellschein_GDH_2026_inkl_MwSt_Mahlzeit_web.pdf
             'Preisliste mit Bestellschein, gültig ab 16. März 2026': article no., name, net weight, price EUR incl. MwSt.
             (robots.txt: Yoast block, ``User-agent: *`` Disallow: (empty) → everything allowed)
  nutrition  https://www.gourmet-daheim.at/downloads → 'Allergene und Nährwerte zur Speisekarte 2026'
             (Sortimentsliste Gourmet Daheim EPTK, gültig ab 16. März 2026): per 100 g kJ/kcal/fat/sat. fat/carbs/sugar/
             protein/salt/BE, allergen letters (Codex) and the menu flags D (Das bewusste Menü), L (Leichte Vollkost),
             GF, LF, SF (ohne Schwein), VEG (vegetarisch). robots.txt: Allow: /, Disallow: /*?* (never used).
The two lists are joined on the 7-digit article number ("23 13122" in the price list = "231 3122" in the nutrition
list). The webshop shopmahlzeit.gourmet.at needs a customer registration for ordering and is not used.
Requests go through the food-connectors polite gate (robots.txt enforced, ≥1 s per host). PDF text is extracted
with poppler's ``pdftotext -layout`` (must be installed). No GTIN, no fibre and no photos are published in these
lists → those fields stay empty (never estimated).

Photos (optional, ``photos=True``): Mahlzeit's own WordPress media library, read through the public REST endpoint
``/wp-json/wp/v2/media`` that the site exposes to every visitor (robots allows all; no auth). Only files whose name
starts with the 7-digit article number (e.g. ``2311070_Schweinsmedaillons_web.jpg``) are mapped — an exact-id match,
no name guessing. Dish photos © GMS Gourmet as published by Mahlzeit; a few date from 2021.
"""
from __future__ import annotations
import re, subprocess, tempfile, os
from .base import Adapter
from ..http import get
from ..schema import Product

STORE = "Online: GOURMET Daheim (Mahlzeit Linz)"
BRAND = "GOURMET Daheim"
PRODUCER = "GMS Gourmet GmbH"
PRICE_PDF = "https://www.mahlzeit.co.at/wp-content/uploads/2026/03/Preisliste_Bestellschein_GDH_2026_inkl_MwSt_Mahlzeit_web.pdf"
DOWNLOADS = "https://www.gourmet-daheim.at/downloads"
NUTRITION_PDF = ("https://www.gourmet-daheim.at/fileadmin/public/Daheim/Downloads/"
                 "Sortimentsliste__Gourmet_Daheim_EPTK___N%C3%A4hrwerte__2026_02_26.pdf")
PRICE_VALID_FROM = "2026-03-16"
MEDIA_API = "https://www.mahlzeit.co.at/wp-json/wp/v2/media"
ART_FILE_RE = re.compile(r"^(\d{7})_[^/]+\.(?:jpe?g|png|webp)$", re.I)
# categories of the price list that are not ready meals (cakes, single cake slices/compote, weekly cartons)
NON_MEAL_CATEGORIES = ("Für Naschkatzen und Kuchentiger", "Der bewusste Genuss", "Wochenkartons", "Saisonale Aktionen")
SECTION_ALIASES = {"Süßes zum Tagträumen": "Süßes zum Träumen", "Grün und Vital": "Grün und vital", "Nudelgerichte": "Nudelgerichte und andre Gedichte"}
FLAG_NAMES = {"D": "Das bewusste Menü", "L": "Leichte Vollkost", "GF": "glutenfrei", "LF": "laktosefrei",
              "SF": "ohne Schweinefleisch", "VEG": "vegetarisch"}

PRICE_RE = re.compile(r"^\s*(\d{2}) (\d{5})\s+(.+?)\s+(?:Breikost\s+)?(\d+) g\s+(\d+,\d{2})\s*$")
NUT_ID_RE = re.compile(r"^(\d{3}) (\d{4})\s+(.*)$")
NUT_TAIL_RE = re.compile(r"(\d+) kJ\s+(\d+) kcal\s+([\d,]+) g\s+([\d,]+) g\s+([\d,]+) g\s+([\d,]+) g\s+([\d,]+) g\s+([\d,]+) g\s+([\d,]+) BE\s*$")
ALLERGEN_RE = re.compile(r"^[A-R](,[A-R])*$")

def _f(s: str) -> float: return float(s.replace(",", "."))

def pdf_text(url: str) -> str:
    b = get(url, raw=True, timeout=60, headers={"Accept": "application/pdf"})
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(b); path = fh.name
    try:
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    finally:
        os.unlink(path)

def _norm_cat(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("Ar tikel", "Artikel").replace("Wochenkar tons", "Wochenkartons").replace("Ak tionen", "Aktionen")).strip()

def parse_prices(text: str) -> list[dict]:
    """Price-list PDF text → [{art, name, size_g, price_eur, category, breikost}] (category = section header)."""
    out, cat = [], None
    for line in text.splitlines():
        m = PRICE_RE.match(line)
        if m:
            art = m.group(1) + m.group(2)
            overflow = cat in ("Wochenkartons", "Saisonale Aktionen")   # rows printed after the carton block (page overflow)
            out.append({"art": art, "name": re.sub(r"\s+", " ", m.group(3)).strip(), "size_g": float(m.group(4)),
                        "price_eur": _f(m.group(5)), "category": None if overflow else cat, "breikost": cat == "Breikost",
                        "overflow": overflow})
            continue
        s = line.strip()
        if s and not re.search(r"\d", s) and len(line) - len(line.lstrip()) >= 20 and not s.startswith("=") \
                and "WWW." not in s and "Preis" not in s and "Menge" not in s and "Breikost" != s or s == "Breikost":
            if len(s) < 45 and not re.match(r"^(Name|Kundennummer|Lieferdatum|nummer|inkl\.MwSt\.)$", s):
                cat = _norm_cat(s)
    return out

def _columns(header: str) -> dict:
    cols = {}
    for k in ("D", "L", "GF", "LF", "SF", "VEG"):
        m = re.search(r"(?<=\s)%s(?=\s)" % k, header)
        if m: cols[k] = m.start()
    m = header.find("Allergene")
    if m >= 0: cols["ALLERG"] = m
    return cols

def parse_nutrition(text: str) -> dict:
    """Nutrition PDF text → {art: {name, nutrition_100g, kj, be, flags[], allergens[], category}}."""
    out, cat, cols, pending = {}, None, {}, None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Art. Nr."):
            cols = _columns(line); continue
        m = NUT_ID_RE.match(line)
        if pending is not None and not m and NUT_TAIL_RE.search(line):
            idline, line, m = pending, line, None
            mid_line = line; pending = None
            mm = NUT_ID_RE.match(idline)
            art, name = mm.group(1) + mm.group(2), mm.group(3).strip()
            body = mid_line
        elif m:
            if not NUT_TAIL_RE.search(line):
                pending = line; continue
            art, body = m.group(1) + m.group(2), line
            # name = text after the id up to the first run of ≥3 spaces
            rest = line[m.start(3):]
            name = re.split(r"\s{3,}", rest.strip())[0]
            pending = None
        else:
            s = line.strip()
            if s and not re.search(r"\d", s) and len(s) < 45 and line == line.lstrip() and not s.startswith(("Allergen", "Die ", "Zutaten", "am ", "allergie", "korrekt", "und ")):
                cat = s
            continue
        t = NUT_TAIL_RE.search(body)
        kj, kcal, fat, sat, carbs, sugar, prot, salt, be = t.groups()
        name_end = body.find(name) + len(name) if name and name in body else 0
        flags, allergens = [], []
        for tm in re.finditer(r"\S+", body[name_end:t.start()]):
            tok, pos = tm.group(0), name_end + tm.start()
            if "ALLERG" in cols and pos >= cols["ALLERG"] - 4 and ALLERGEN_RE.match(tok):
                allergens = tok.split(","); continue
            for f in ("GFLF",) if tok == "GFLF" else (tok,):
                if f == "GFLF": flags += ["GF", "LF"]
                elif f in FLAG_NAMES: flags.append(f)
        name = name.strip()
        while True:
            n2 = re.sub(r"\s+(LVK|GF ?LF|GFLF|GF|LF|ZR|BREIKOST|BREIKOS)$", "", name)
            if n2 == name: break
            name = n2
        out[art] = {"art": art, "name": name, "category": cat, "kj": int(kj), "be": _f(be), "flags": sorted(set(flags)),
                    "allergens": allergens, "nutrition_100g": {"kcal": float(kcal), "fat": _f(fat), "satfat": _f(sat),
                    "carbs": _f(carbs), "sugar": _f(sugar), "protein": _f(prot), "salt": _f(salt)}}
    return out

def nutrition_pdf_url() -> str:
    """Current 'Allergene und Nährwerte' PDF linked on gourmet-daheim.at/downloads (falls back to the 2026-02-26 file)."""
    try:
        h = get(DOWNLOADS, raw=True).decode("utf-8", "replace")
        m = re.search(r'href="(/fileadmin/[^"]*N%C3%A4hrwerte[^"]*\.pdf)"', h)
        if m: return "https://www.gourmet-daheim.at" + m.group(1)
    except Exception:
        pass
    return NUTRITION_PDF

def photos_from_media(items: list[dict]) -> dict:
    """WP media items → {article_no: image_url}; only '<7-digit art no>_….jpg' files, '_cropped' derivatives skipped."""
    out = {}
    for m in sorted(items, key=lambda m: m.get("date") or ""):
        url = m.get("source_url") or ""
        fn = url.rsplit("/", 1)[-1]
        mm = ART_FILE_RE.match(fn)
        if mm and "cropped" not in fn.lower():
            out.setdefault(mm.group(1), url)
    return out

def article_photos(max_pages: int = 10) -> dict:
    items = []
    for page in range(1, max_pages + 1):
        try:
            batch = get(f"{MEDIA_API}?per_page=100&page={page}&_fields=source_url,date&media_type=image")
        except Exception:
            break   # WP answers 400 past the last page
        if not isinstance(batch, list) or not batch: break
        items += batch   # WP may return < per_page on full pages (hidden items) → page on until empty/400
    return photos_from_media(items)

def is_meal(row: dict) -> bool:
    return bool(row.get("category")) and row.get("category") not in NON_MEAL_CATEGORIES

def join(prices: list[dict], nut: dict, price_url: str = PRICE_PDF, nut_url: str = NUTRITION_PDF,
         photos: dict | None = None) -> list[Product]:
    out, photos = [], photos or {}
    for r in prices:
        n = nut.get(r["art"]) or {}
        if r.get("overflow") or not r.get("category"):
            r = dict(r, category=SECTION_ALIASES.get(n.get("category"), n.get("category")))
        flags = n.get("flags") or []
        out.append(Product(source="gourmet-daheim", store=STORE, name=r["name"], brand=BRAND, price_eur=r["price_eur"],
            unit_price_eur=round(r["price_eur"] / r["size_g"] * 1000, 2) if r["size_g"] else None, unit="kg", size_g=r["size_g"],
            nutrition_100g=n.get("nutrition_100g") or {}, producer=PRODUCER, origin=None, category=r["category"],
            source_url=price_url, source_id=r["art"], image_url=photos.get(r["art"]),
            extra={"article_no": f"{r['art'][:2]} {r['art'][2:]}", "price_valid_from": PRICE_VALID_FROM, "price_incl_vat": True,
                   "storage": "tiefgekühlt (-18 °C)", "breikost": r["breikost"], "flags": flags,
                   "flag_names": [FLAG_NAMES[f] for f in flags], "vegetarian": "VEG" in flags, "allergens": n.get("allergens"),
                   "kj_100g": n.get("kj"), "be_100g": n.get("be"), "nutrition_name": n.get("name"),
                   "nutrition_source": nut_url if n else None, "is_meal": is_meal(r) and r["size_g"] >= 150,
                   "delivery": "Mahlzeit Vertriebs GmbH Linz: wöchentliche TK-Zustellung in ganz Oberösterreich, ab 1 Karton (7 Hauptspeisen) gratis"}))
    return out

class GourmetDaheim(Adapter):
    id = "gourmet-daheim"; store = STORE; homepage = "https://www.mahlzeit.co.at/a-la-carte/"
    notes = ("GOURMET Daheim frozen à-la-carte menus delivered in Upper Austria by Mahlzeit Vertriebs GmbH (Linz): official price-list PDF "
             "(mahlzeit.co.at) joined with the official allergen/nutrition PDF (gourmet-daheim.at) on the article number; dish photos "
             "only where Mahlzeit's public WP media library has a file named by the article number. No GTIN.")
    photos = True
    def _all(self) -> list[Product]:
        nu = nutrition_pdf_url()
        ph = article_photos() if self.photos else {}
        return join(parse_prices(pdf_text(PRICE_PDF)), parse_nutrition(pdf_text(nu)), PRICE_PDF, nu, ph)
    def fetch(self, category: str = "ready-meals", limit: int = 500) -> list[Product]:
        ps = self._all()
        if category == "ready-meals": ps = [p for p in ps if p.extra.get("is_meal")]
        elif category != "all": return self.search(category, limit)
        return ps[:limit]
    def search(self, q: str, limit: int = 50) -> list[Product]:
        words = [w for w in re.split(r"\W+", q.lower()) if w]
        return [p for p in self._all() if all(w in p.name.lower() for w in words)][:limit]

def product(art: str) -> Product | None:
    a = re.sub(r"\D", "", art or "")
    return next((p for p in GourmetDaheim()._all() if p.source_id == a), None)
