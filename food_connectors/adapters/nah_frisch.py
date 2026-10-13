"""Nah&Frisch Österreich — live connector for the public "Angebote der Woche" page (weekly offers).

Access path (no login, no cookies, no browser): the server-rendered HTML page
  https://www.nahundfrisch.at/de/aktuelles/angebote-der-woche
robots.txt (nahundfrisch.at, checked 2026-10-13): 'User-agent: * Allow: /' — only /build /css /fonts /images /js /storage
are disallowed; offer tiles are served from /media/cache/resize_w500/Angebote_der_Woche/... (allowed).
The page has one tab per calendar week (button label 'KW 41 7. Oktober 2026 - 13. Oktober 2026 *') holding a grid of
offer tiles. Each tile is an image only (alt=""), 355×455 px, fixed template: brand + name (bold italic, left),
pack text ('versch. Sorten', '350-400 g-Pkg.') on the green band, price in the red box (cents superscript),
optional yellow badge ('1+1 gratis', 'Günstiger! Ab 2 Pkg. je', '25% billiger') and a unit-price line '(100 g = …)'.
There is no structured product data — so `offers()` returns the tiles with week/validity, and `to_product()` OCRs the
tile with a local `tesseract` (deu) when installed (fields flagged `extra.ocr=True` + raw text; verify before use).
No GTIN, no nutrition — combine with `off` or EAN twins from other stores. Offers are valid only in participating
Nah&Frisch markets (franchise). Nah&Frisch has no webshop.
"""
from __future__ import annotations
import datetime as dt, html, io, re, shutil, subprocess, tempfile, os
from ..http import get
from ..schema import Product
from .base import Adapter

BASE = "https://www.nahundfrisch.at"
PAGE = BASE + "/de/aktuelles/angebote-der-woche"
MONTHS = {m: i + 1 for i, m in enumerate(["jänner", "februar", "märz", "april", "mai", "juni", "juli", "august",
                                           "september", "oktober", "november", "dezember"])}
MONTHS["januar"] = 1
MEAL_WORDS = ("fertiggericht", "suppe", "eintopf", "gulasch", "knödel", "pizza", "lasagne", "strudel", "nudel",
              "teller", "menü", "ravioli", "tortellini", "gnocchi", "risotto", "curry", "chili", "beuschel", "paprika")

def _date(d, mon, y):
    m = MONTHS.get(mon.lower())
    return dt.date(int(y), m, int(d)).isoformat() if m else None

def parse_page(text: str) -> list[dict]:
    """→ [{tab, label, kw, valid_from, valid_to, tiles:[url,…]}] in page order."""
    labels = {}
    for m in re.finditer(r'data-bs-target="#([^"]+)"[^>]*>\s*(.*?)\s*</button>', text, re.S):
        lab = re.sub(r"\s+", " ", html.unescape(m.group(2))).strip()
        r = re.search(r"KW\s*(\d+)\s+(\d+)\.\s*(\w+)\s+(\d{4})\s*-\s*(\d+)\.\s*(\w+)\s+(\d{4})", lab)
        labels[m.group(1)] = dict(label=lab, kw=int(r.group(1)) if r else None,
                                  valid_from=_date(*r.group(2, 3, 4)) if r else None, valid_to=_date(*r.group(5, 6, 7)) if r else None)
    out = []
    for part in re.split(r'<div class="tab-pane', text)[1:]:
        tid = re.search(r'id="([^"]+)"', part).group(1)
        tiles = []
        for u in re.findall(r'<img[^>]+src="(/media/[^"]*Angebote_der_Woche/[^"]+)"', part):
            u = BASE + u
            if u not in tiles: tiles.append(u)
        out.append(dict(tab=tid, tiles=tiles, **labels.get(tid, dict(label=None, kw=None, valid_from=None, valid_to=None))))
    return out

def offers(text: str | None = None) -> list[dict]:
    """One dict per offer tile: {tile_url, tile_no, kw, valid_from, valid_to, week_label}."""
    text = text if text is not None else get(PAGE, raw=True, timeout=30).decode("utf-8", "replace")
    res = []
    for wk in parse_page(text):
        for i, u in enumerate(wk["tiles"], 1):
            res.append(dict(tile_url=u, tile_no=i, kw=wk["kw"], valid_from=wk["valid_from"], valid_to=wk["valid_to"], week_label=wk["label"]))
    return res

# ---------- OCR (optional, needs `tesseract` with deu + Pillow) ----------
def _tess(img, psm=6, extra=()):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name); p = f.name
    try:
        r = subprocess.run(["tesseract", p, "-", "-l", "deu", "--psm", str(psm), *extra], capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    finally:
        os.unlink(p)

def _bands(im):
    """Find the green pack band top and the red price box (bbox) on a 355×455 tile."""
    W, H = im.size; px = im.load()
    red = [sum(1 for x in range(W) if px[x, y][0] > 200 and px[x, y][1] < 70 and px[x, y][2] < 70) for y in range(H)]
    green = [sum(1 for x in range(W // 2) if px[x, y][1] > 170 and px[x, y][1] - px[x, y][0] > 15 and px[x, y][2] < 140) for y in range(H)]
    gtop = next((y for y in range(H // 2, H) if green[y] > W * 0.3), int(H * 0.82))
    rys = [y for y in range(H // 2, H) if red[y] > 40]
    box = None
    if rys:
        y0, y1 = rys[0], rys[-1]
        xs = [x for x in range(W) if sum(1 for y in range(y0, y1 + 1, 3) if px[x, y][0] > 200 and px[x, y][1] < 70 and px[x, y][2] < 70) > (y1 - y0) / 6]
        if xs: box = (xs[0], y0, xs[-1], y1)
    return gtop, box

CLEAN = re.compile(r"^[A-ZÄÖÜa-zäöüß0-9%’'&.,!\- ]+$")
def _name_lines(txt):
    """Keep the trailing run of clean text lines (brand + product name); drop OCR noise from the packshot above."""
    ls = [l.strip() for l in txt.splitlines() if l.strip()]
    out = []
    for l in reversed(ls):
        if CLEAN.match(l) and re.search(r"[A-Za-zÄÖÜäöü]{3}", l) and not re.search(r"\b[a-z]{1,2}\b\s*$", l): out.append(l)
        else: break
    return list(reversed(out))[-4:]

def _ocr_price(c):
    """Red price box: big euro digits + superscript cents. Split glyph columns by height and OCR both parts."""
    from PIL import ImageOps
    g = ImageOps.grayscale(c).point(lambda v: 255 if v > 200 else 0)  # white digits → 255
    W, H = g.size; px = g.load()
    cols = []
    for x in range(W):
        ys = [y for y in range(H) if px[x, y] == 255]
        cols.append((min(ys), max(ys)) if len(ys) > 1 else None)
    segs, cur = [], None
    for x, c_ in enumerate(cols + [None]):
        if c_ and cur is None: cur = [x, x, c_[0], c_[1]]
        elif c_: cur[1] = x; cur[2] = min(cur[2], c_[0]); cur[3] = max(cur[3], c_[1])
        elif cur: segs.append(cur); cur = None
    segs = [s for s in segs if s[1] - s[0] >= 2 and s[3] - s[2] >= H * 0.15]
    if not segs: return None, ""
    hmax = max(s[3] - s[2] for s in segs)
    big = [s for s in segs if s[3] - s[2] >= 0.7 * hmax]; small = [s for s in segs if s[3] - s[2] < 0.7 * hmax and s[0] > big[-1][1] - 2] if big else []
    inv = lambda im: ImageOps.invert(im).resize((im.width * 3, im.height * 3))
    wl = ("-c", "tessedit_char_whitelist=0123456789")
    pad = lambda x0, x1, y0, y1: g.crop((max(0, x0 - 6), max(0, y0 - 6), min(W, x1 + 7), min(H, y1 + 7)))
    e = re.sub(r"\D", "", _tess(inv(pad(big[0][0], big[-1][1], min(s[2] for s in big), max(s[3] for s in big))), 7, wl)) if big else ""
    ct = re.sub(r"\D", "", _tess(inv(pad(small[0][0], small[-1][1], min(s[2] for s in small), max(s[3] for s in small))), 7, wl)) if small else ""
    txt = f"{e}|{ct}"
    if e and len(ct) == 2 and len(e) <= 3: return round(int(e) + int(ct) / 100, 2), txt
    return None, txt

def ocr_tile(png: bytes) -> dict:
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(png)).convert("RGB"); W, H = im.size
    gtop, box = _bands(im)
    xr = box[0] - 4 if box else int(W * 0.6)
    up = lambda c: ImageOps.grayscale(c).resize((c.width * 3, c.height * 3))
    name = _tess(up(im.crop((0, int(H * 0.55), max(xr, int(W * 0.55)), gtop))), 6)
    pack = _tess(up(im.crop((0, gtop, max(xr, int(W * 0.55)), H))), 6)
    price = None; ptxt = ""
    if box:
        price, ptxt = _ocr_price(im.crop(box))
    lines = _name_lines(name)
    by = box[1] if box and box[1] > int(H * 0.55) + 10 else H
    badge = _tess(up(im.crop((int(W * 0.55), int(H * 0.55), W, by))), 6)
    return dict(name_lines=lines, pack_text=" ".join(l.strip() for l in pack.splitlines() if l.strip()), price_eur=price,
                price_ocr=ptxt, badge_text=" ".join(badge.split()), green_top=gtop, price_box=box)

def to_product(o: dict, ocr: bool | None = None) -> Product:
    ocr = shutil.which("tesseract") is not None if ocr is None else ocr
    x = dict(o, ocr=False); name = f"Nah&Frisch Angebot KW{o.get('kw')} #{o.get('tile_no')}"; brand = None; price = None
    if ocr:
        try:
            r = ocr_tile(get(o["tile_url"], raw=True, timeout=30)); x.update(r, ocr=True)
            if r["name_lines"]:
                brand = r["name_lines"][0]; name = " ".join(r["name_lines"])
            price = r["price_eur"]
        except Exception as e:
            x["ocr_error"] = str(e)[:200]
    unit = re.search(r"\(\s*100\s*g\s*=\s*([\d,\-–]+)\s*\)", x.get("pack_text") or "")
    return Product(source="nah-frisch", store="Nah&Frisch", name=name, brand=brand, price_eur=price, image_url=o["tile_url"],
                   source_url=PAGE, source_id=o["tile_url"].rsplit("/", 1)[-1].rsplit(".", 1)[0],
                   extra=dict(x, unit_price_100g_text=unit.group(1) if unit else None,
                              note="Weekly offer tile (image only); OCR fields need visual verification; valid only in participating markets"))

def is_ready_meal(p: Product) -> bool:
    t = (p.name or "").lower(); return any(w in t for w in MEAL_WORDS)

class NahFrisch(Adapter):
    id = "nah-frisch"; store = "Nah&Frisch"; homepage = BASE; status = "live"
    notes = ("Live (offers only): Nah&Frisch 'Angebote der Woche' page (robots Allow, no login/cookies) — weekly offer tiles per KW with "
             "validity; tiles are images only, names/prices via optional local tesseract OCR (extra.ocr). No webshop, no GTIN/nutrition.")
    def search(self, q: str, limit: int = 20) -> list[Product]:
        ql = q.lower(); ps = [to_product(o) for o in offers()]
        return [p for p in ps if ql in (p.name or "").lower()][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 200) -> list[Product]:
        ps = [to_product(o) for o in offers()]
        if category == "ready-meals": ps = [p for p in ps if is_ready_meal(p)]
        elif category != "all": ps = [p for p in ps if category.lower() in (p.name or "").lower()]
        return ps[:limit]
