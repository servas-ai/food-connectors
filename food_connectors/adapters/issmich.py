"""iss mich! (issmich.at) — Wiener Bio-Eintöpfe, Suppen & Beilagen im WECK-Pfandglas, Versand österreichweit.

Sources (public, no login/cookies; robots.txt ``User-agent: * Allow: /`` — only ``*/?``, account, checkout,
widgets, navigation, bundles and the imprint/privacy/gtc *English* aliases are disallowed):
  * sitemap ``https://www.issmich.at/sitemap.xml`` → Shopware 6 sales-channel ``…sitemap-www-issmich-at-1.xml.gz``
    (product URLs under ``/Bio-Shop/…`` plus a few root-level product slugs) and the category listing pages
    (``/Eintoepfe``, ``/Suppen``, ``/beilagen``, ``/suesspeise``, ``/saucen``, ``/sale``) for ``a.product-name`` links.
  * product page (Shopware 6 storefront, schema.org microdata): ``itemprop`` name/sku/productID/gtin13/weight,
    Offer price (EUR incl. MwSt.) + optional list price (Streichpreis), ``zzgl. 2,00 € Pfand`` (WECK glass deposit),
    ``Inhalt: 280 Gramm``, availability, gallery images; description with ``Zutaten:`` and ``Allergene:``.
  * the Nährwerttabelle is published only as an image (``/media/…/NT_<code> <name>_iss mich!_1.jpg``, pro 100 g +
    pro Portion). ``parse_nutrition_image`` OCRs it with a local ``tesseract`` (deu) when installed and accepts the
    result ONLY if every row is consistent with the printed per-portion column (per100 × portion/100) and with
    Atwater kcal; otherwise nutrition stays empty and ``extra['nutrition_image']`` points at the official table.
    The Daten-Squad snapshot (fertiggerichte-daten raw/issmich_*.json) carries vision-verified transcriptions.
Ready meals = Eintöpfe + Suppen (incl. Kraftsuppe); Beilagen (Semmelknödel), Süßes, Saucen and WECK-Zubehör are
tagged ``extra['course']`` and excluded by ``is_ready_meal``.
Shipping (``/versand-und-bezahlung``): Österreich only, Post (Versand montags) + Wien Fahrrad/Auto, 9,90 €,
versandkostenfrei ab 99 €; Selbstabholung Fr 10–13 Uhr, Erlafstraße 7, 1020 Wien. Glas-Pfand 2,00 € per jar.
Operator: iss mich! GmbH, Erlafstraße 7, 1020 Wien, FN 471722i (HG Wien; evi.gv.at), UID ATU72305301 (VIES valid
2026-10-14), Bio-Kontrollstelle AT-BIO-401 (Impressum). Polite 1 req/s.
"""
from __future__ import annotations
import gzip, html as _html, itertools, os, re, shutil, subprocess, tempfile, time, urllib.request
from .base import Adapter
from ..http import get, UA
from ..schema import Product

BASE = "https://www.issmich.at"
STORE = "Online: iss mich!"
PRODUCER = "iss mich! GmbH, Erlafstraße 7, 1020 Wien, FN 471722i"
SHIPPING_EUR = 9.90
SHIPPING_NOTE = ("nur Österreich (Post, Versand montags; Wien auch per Fahrrad/Auto): 9,90 €, versandkostenfrei ab 99 € "
                 "lt. issmich.at/versand-und-bezahlung; zzgl. 2,00 € Pfand je WECK-Glas; Selbstabholung Fr 10–13 Uhr 1020 Wien")
LISTINGS = ("Eintoepfe", "Suppen", "beilagen", "suesspeise", "saucen", "sale")
MEAL_COURSES = ("Eintopf", "Suppe")
NUT_KEYS = ("kcal", "fat", "satfat", "carbs", "sugar", "protein", "salt")


def _html_get(url: str) -> str:
    return get(url, raw=True, timeout=40, headers={"Accept": "text/html,application/xhtml+xml;q=0.9"}).decode("utf-8", "replace")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _num(s):
    try:
        return float(str(s).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


# ---------------- discovery ----------------
def sitemap_urls() -> list[str]:
    idx = get(f"{BASE}/sitemap.xml", raw=True, timeout=30).decode("utf-8", "replace")
    out = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", idx):
        b = get(loc.strip(), raw=True, timeout=40)
        if b[:2] == b"\x1f\x8b":
            b = gzip.decompress(b)
        out += re.findall(r"<loc>([^<]+)</loc>", b.decode("utf-8", "replace"))
        time.sleep(1.0)
    return out


def listing_urls(html: str) -> list[str]:
    return re.findall(r'href="(https://www\.issmich\.at/[^"]+)"[^>]*class="product-name', html)


def product_urls(delay: float = 1.0) -> list[str]:
    urls = {u for u in sitemap_urls() if "/Bio-Shop/" in u}
    for c in LISTINGS:
        time.sleep(delay)
        try:
            urls |= set(listing_urls(_html_get(f"{BASE}/{c}")))
        except Exception:
            pass
    return sorted(urls)


# ---------------- product page ----------------
def _course(url: str, name: str, crumbs: str) -> str:
    u = url.lower(); n = name.lower()
    if "/zubehoer/" in u or "weck" in n and ("klammer" in n or "ring" in n):
        return "Zubehör"
    if "/beilagen/" in u or "knödel" in n or "spätzle" in n:
        return "Beilage"
    if "/suesses/" in u or "milchreis" in n or "souffl" in n:
        return "Süßspeise"
    if "/saucen/" in u or "ragu" in n:
        return "Sauce"
    if "/suppen/" in u or "suppe" in n or "brühe" in n:
        return "Suppe"
    return "Eintopf"


def parse_page(h: str, url: str) -> dict:
    g = lambda rx: (m.group(1).strip() if (m := re.search(rx, h, re.S)) else None)
    name = _clean(g(r'<h1[^>]*product-detail-name[^>]*>(.*?)</h1>') or "")
    seasonal = re.search(r"\(Saisonal_(\w+)\)", name)
    name_clean = re.sub(r"\s*\(Saisonal_\w+\)", "", name).strip()
    price = _num(g(r'itemprop="price" content="([\d.]+)"'))
    lp = g(r'class="list-price-price">\s*([\d.,]+)\s*€')
    deposit = _num(g(r"zzgl\.\s*([\d,]+)\s*€\s*Pfand"))
    size = _num(g(r'price-unit-content">\s*([\d,]+)\s*Gramm'))
    gtin = g(r'itemprop="gtin13" content="(\d{8,14})"')
    avail = g(r'itemprop="availability" href="[^"]*/(\w+)"')
    imgs = []
    for tag in re.findall(r"<img\b[^>]*gallery-slider-image[^>]*>", h):  # product gallery only (not the site logo)
        m = re.search(r'itemprop="image" content="(https://www\.issmich\.at/media/[^"]+)"', tag)
        if m and m.group(1) not in imgs and "logo" not in m.group(1).lower():
            imgs.append(m.group(1))
    nt = [u for u in imgs if re.search(r"/NT(?:_|%20)", u)]
    packs = [u for u in imgs if u not in nt]
    desc = h[h.find("product-detail-description"):] if "product-detail-description" in h else ""
    plain = _clean(desc[:20000])
    ing = re.search(r"Zutaten:\s*(.*?)\s*(?:mit \* gekennzeichnete|\*Alle Zutaten|Allergene:|$)", plain, re.S)
    alg = re.search(r"Allergene:\s*(.*?)(?=\s(?:Vegan|Vegetarisch|Laktosefrei|Glutenfrei|Ohne|Das Gericht|Menü schließen|Produktnummer)\b|$)", plain)
    veg_label = None
    for lab in ("Vegan", "Vegetarisch"):
        if re.search(rf"/Bio-Shop/[^/]+/{lab}/", url) or re.search(rf"/{lab.lower()}", url.lower()):
            veg_label = lab
    return {
        "name": name_clean, "name_raw": name, "seasonal": seasonal.group(1) if seasonal else None,
        "price_eur": price, "list_price_eur": _num(lp) if lp else None, "deposit_eur": deposit, "size_g": size,
        "gtin": gtin, "sku": g(r'itemprop="sku">\s*([^<]+?)\s*<'), "shopware_id": g(r'itemprop="productID" content="([0-9a-f]+)"'),
        "available": (avail == "InStock") if avail else None, "availability": avail,
        "images": packs, "nutrition_image": nt[0] if nt else None,
        "ingredients": ing.group(1).strip() if ing else None,
        "allergens": alg.group(1).strip().rstrip(".") if alg else None,
        "course": _course(url, name_clean, ""), "veg_label": veg_label,
    }


def gtin_ok(code: str | None) -> bool:
    if not code or not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    d = [int(c) for c in code]; chk = d.pop()
    s = sum(x * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(d)))
    return (10 - s % 10) % 10 == chk


# ---------------- nutrition image OCR (strict, optional) ----------------
_LABELS = (("satfat", r"ges[äa]tt|fetts[äa]u"), ("sugar", r"zucker"), ("carbs", r"kohlen|hydrat"),
           ("protein", r"eiwei|protein"), ("salt", r"^\W*sal[zt]?\b"), ("fat", r"^\W*fett\b"))


def _cands(tok: str, decimals: int = 1) -> list[float]:
    """OCR token → plausible readings, best first. The table prints N,N g (salt per 100 g: N,NN g); tesseract often
    reads the unit 'g' as a trailing '9' ('7,39' = 7,3 g) and sometimes drops the comma ('739' = 7,3 g)."""
    t = re.sub(r"[^\d,]", "", tok.replace("O", "0").replace(".", ","))
    if not re.search(r"\d", t):
        return []
    fmt = re.compile(r"\d+(?:,\d{1,%d})?" % decimals)
    out = []
    def add(s):
        s = s.strip(",")
        if s and s.count(",") <= 1:
            v = round(float(s.replace(",", ".")), 2)
            if v not in out:
                out.append(v)
    if t.endswith("9") and len(t) > 1 and fmt.fullmatch(t[:-1]) and not fmt.fullmatch(t):
        add(t[:-1])                       # '7,39' → 7,3 (g→9)
    if fmt.fullmatch(t):
        add(t)
    if t.endswith("9") and len(t) > 1 and fmt.fullmatch(t[:-1]):
        add(t[:-1])
    if "," not in t:  # comma lost
        for bb in ([t[:-1]] if t.endswith("9") and len(t) > 1 else []) + [t]:
            for i in range(1, decimals + 1):
                if len(bb) > i:
                    add(bb[:-i] + "," + bb[-i:])
    return out


def _ocr_texts(path: str) -> list[str]:
    from PIL import Image  # optional dependency
    out = []
    for scale, psm in ((1, 4), (1, 11), (2, 3)):
        im = Image.open(path).convert("L")
        if scale > 1:
            im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
        fd, t = tempfile.mkstemp(suffix=".png"); os.close(fd); im.save(t)
        try:
            out.append(subprocess.run(["tesseract", t, "-", "-l", "deu", "--psm", str(psm)],
                                      capture_output=True, text=True, timeout=90).stdout)
        finally:
            os.unlink(t)
    return out


def solve_ocr(texts: list[str], portion: float) -> tuple[dict, dict]:
    r = portion / 100.0
    per100, perp = {}, {}
    for key, rx in _LABELS:
        best = None
        for txt in texts:
            for line in txt.splitlines():
                if not re.search(rx, line.strip().lower()):
                    continue
                toks = [x for x in re.findall(r"[\dO][\dO,.]*", line) if re.search(r"\d", x)]
                if len(toks) < 2:
                    continue
                for (ia, a), (ib, b) in itertools.product(enumerate(_cands(toks[0], 2 if key == "salt" else 1)), enumerate(_cands(toks[-1], 1))):
                    err = abs(a * r - b)
                    score = (ia + ib, err)  # prefer format-exact readings, then the closest per-portion match
                    if err <= max(0.06 + 0.051 * r, 0.02 * b) and (best is None or score < best[0]):
                        best = (score, a, b)
        if best:
            per100[key], perp[key] = best[1], best[2]
    kc = []
    for txt in texts:
        kc += [float(x.replace(",", ".")) for x in re.findall(r"(\d+[,.]\d)\s*kcal", txt)]
    best = None
    for a, b in itertools.permutations(set(kc), 2):
        err = abs(a * r - b)
        if err <= max(1.0, 0.012 * b) and (best is None or err < best[0]):
            best = (err, a, b)
    if best:
        per100["kcal"], perp["kcal"] = best[1], best[2]
    return per100, perp


def nutrition_problems(n: dict) -> list[str]:
    bad = [f"missing {k}" for k in ("kcal", "fat", "carbs", "protein", "salt") if n.get(k) is None]
    if bad:
        return bad
    if n.get("satfat", 0) > n["fat"] + 0.05:
        bad.append("satfat>fat")
    if n.get("sugar", 0) > n["carbs"] + 0.05:
        bad.append("sugar>carbs")
    est = 4 * n["carbs"] + 4 * n["protein"] + 9 * n["fat"]
    if abs(est - n["kcal"]) > max(10, 0.12 * n["kcal"]):
        bad.append(f"kcal {n['kcal']} vs Atwater {est:.0f}")
    return bad


def nutrition_from_file(path: str, portions=(280.0,)) -> dict:
    texts = _ocr_texts(path)
    cand = set(p for p in portions if p)
    for t in texts:
        cand |= {float(m.group(1)) for m in re.finditer(r"Portion\s*\(\s*(\d{3}),0\s*g\)", t)}
    best = None
    for p in sorted(cand):
        a, b = solve_ocr(texts, p)
        sc = (not nutrition_problems(a), len(a))
        if best is None or sc > best[0]:
            best = (sc, a, b, p)
    _, a, b, p = best
    probs = nutrition_problems(a)
    return {"per100": a if not probs else {}, "per_portion": b if not probs else {}, "portion_g": p if not probs else None,
            "ocr_ok": not probs, "problems": probs, "ocr_raw": a}


def parse_nutrition_image(url: str, portions=(280.0,)) -> dict:
    """OCR the official Nährwerttabelle image (strict). Returns {'per100','per_portion','portion_g','ocr_ok','problems'}."""
    if not url or not shutil.which("tesseract"):
        return {"per100": {}, "per_portion": {}, "portion_g": None, "ocr_ok": False, "problems": ["no tesseract/image"]}
    fd, path = tempfile.mkstemp(suffix=".jpg"); os.close(fd)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=40) as r:
            open(path, "wb").write(r.read())
        return nutrition_from_file(path, portions)
    finally:
        os.unlink(path)


# ---------------- product ----------------
def to_product(d: dict, url: str, nut: dict | None = None) -> Product:
    nut = nut or {}
    per100 = dict(nut.get("per100") or {})
    price, size = d["price_eur"], d["size_g"]
    gtin = d["gtin"] if gtin_ok(d["gtin"]) else None
    vegan = d["veg_label"] == "Vegan" or bool(re.search(r"\bvegan", d["name"], re.I))
    return Product(
        source="issmich", store=STORE, name=d["name"], brand="iss mich!",
        price_eur=price,
        unit_price_eur=round(price / size * 1000, 2) if price and size else None,
        unit="kg" if price and size else None, size_g=size,
        nutrition_100g={k: per100[k] for k in NUT_KEYS if per100.get(k) is not None},
        ean=gtin, image_url=d["images"][0] if d["images"] else None, producer=PRODUCER, origin="AT (Wien)",
        category="Fertiggericht" if d["course"] in MEAL_COURSES else d["course"],
        source_url=url, source_id=d["sku"],
        extra={
            "course": d["course"], "seasonal": d["seasonal"], "name_raw": d["name_raw"],
            "list_price_eur": d["list_price_eur"], "deposit_eur": d["deposit_eur"],
            "available": d["available"], "availability": d["availability"], "gtin_raw": d["gtin"],
            "shopware_id": d["shopware_id"], "images": d["images"], "nutrition_image": d["nutrition_image"],
            "pack_nutrition": nut.get("per_portion") or {}, "portion_g": nut.get("portion_g"),
            "nut_ocr": bool(nut.get("ocr_ok")), "nut_problems": nut.get("problems"),
            "ingredients": d["ingredients"], "allergens": d["allergens"],
            "vegan": vegan, "vegetarian": vegan or d["veg_label"] == "Vegetarisch", "bio": True, "bio_code": "AT-BIO-401",
            "packaging": "WECK-Pfandglas", "shipping_eur": SHIPPING_EUR, "shipping_note": SHIPPING_NOTE,
        },
    )


def product(url: str, ocr: bool | None = None) -> Product | None:
    if not url.startswith("http"):
        url = f"{BASE}/{url.lstrip('/')}"
    h = _html_get(url)
    if "product-detail-buy" not in h:
        return None
    d = parse_page(h, url)
    nut = None
    ocr = shutil.which("tesseract") is not None if ocr is None else ocr
    if ocr and d["nutrition_image"]:
        try:
            nut = parse_nutrition_image(d["nutrition_image"], portions=(d["size_g"] or 280.0, 280.0))
        except Exception as e:
            nut = {"problems": [f"ocr error {e!r}"[:80]]}
    return to_product(d, url, nut)


def is_ready_meal(p: Product) -> bool:
    return bool(p.name) and bool(p.price_eur) and bool(p.size_g) and p.extra.get("course") in MEAL_COURSES


class IssMich(Adapter):
    id = "issmich"
    store = STORE
    homepage = BASE
    notes = ("Live: Shopware 6 storefront (sitemap + category listings → product pages with schema.org microdata: "
             "price, Streichpreis, Pfand, Inhalt, GTIN-13, SKU, availability, images, Zutaten/Allergene); Nährwerte "
             "only as official table image → optional strict tesseract OCR (per-portion + Atwater consistency) else "
             "extra.nutrition_image; Bio Eintöpfe/Suppen im WECK-Glas, Versand nur AT 9,90 € (frei ab 99 €); 1 req/s")
    delay = 1.0

    def fetch(self, category="ready-meals", limit=500, ocr: bool | None = None):
        out = []
        for u in product_urls(self.delay):
            if len(out) >= limit:
                break
            time.sleep(self.delay)
            try:
                p = product(u, ocr=ocr)
            except Exception:
                continue
            if p and (category != "ready-meals" or is_ready_meal(p)):
                out.append(p)
        return out

    def search(self, q, limit=50):
        tr = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
        words = [w.lower().translate(tr) for w in re.findall(r"\w{3,}", q)]
        hits = [u for u in product_urls(self.delay) if all(w in u.lower().replace("-", " ") for w in words)]
        out = []
        for u in hits[:limit]:
            time.sleep(self.delay)
            p = product(u)
            if p:
                out.append(p)
        return out
