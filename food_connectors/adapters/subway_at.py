"""Subway Österreich — live connector for the AT menu (subway.com/de-AT).

Access path (no login, no cookies kept, no JS):
  category pages https://www.subway.com/de-AT/MenuNutrition/Menu/<Category> (server-rendered; 302 to the
  lower-case path, followed). Each product tile is
  ``<div id="MenuCatProduct_<ProductId>">`` + ``<a href=.../Product?ProductId=..&MenuCategoryId=..>`` +
  ``<img title="<description>" src="/de-at/ns/images/menu/AST/GER/<file>" alt="<name>">`` + ``<h3>`` name.
  Product detail pages answer 'Not found' to non-browser clients, so only category tiles are used.
robots.txt (checked 2026-10-17): ``User-agent: *`` disallows only /sitecore/ and non-AT /deliverylocator paths.
Requests go through the food-connectors polite gate (robots.txt enforced, ≥1 s per host).

The AT site publishes NO prices (franchise pricing) → price stays empty. Nutrition for AT is published as a PDF
(subway.com/v1v2/assets/de-at/nutrition/documents/...); this adapter returns the menu tiles (name, description,
official tile photo, category, Subway ProductId). Generic tiles ('Wraps', 'Salate', 'Chips', 'Kaffee') describe a
whole product group, flagged ``extra.generic_tile`` so they are never used as a specific dish photo.
"""
from __future__ import annotations
import html as _html, re
from .base import Adapter
from ..http import get
from ..schema import Product

BASE = "https://www.subway.com"
MENU = BASE + "/de-AT/MenuNutrition/Menu/"
STORE = "Subway"
# category slug → label; MEAL_CATS = dishes (subs, panini, creations, wraps/salads, breakfast, kids)
CATEGORIES = {"Sandwiches": "Subs", "SubMelts": "Sub Melts (Panini)", "SubwaySeries": "Unsere Kreationen",
              "Salads-and-Wraps": "Salate & Wraps", "Breakfast": "Frühstück", "Kids": "Kids' Pak",
              "Subway-Snacks": "Subway Snacks", "Sidekicks": "Sidekicks", "SidesDrinksExtras": "Cookies, Drinks & Co."}
MEAL_CATS = ("Sandwiches", "SubMelts", "SubwaySeries", "Salads-and-Wraps", "Breakfast", "Kids")
GENERIC = {"wraps", "salate", "cookies", "chips", "kaffee", "flaschengetränke", "käse", "bacon"}
TILE_RE = re.compile(r'<div id="MenuCatProduct_(\d+)"[^>]*>\s*<a href="([^"]+)"[^>]*>\s*<img([^>]*)>\s*<h3[^>]*>(.*?)</h3>', re.S)

def _a(attrs: str, k: str) -> str | None:
    m = re.search(r'\b%s="([^"]*)"' % k, attrs)
    return re.sub(r"\s+", " ", _html.unescape(m.group(1))).strip() if m else None

def parse_tiles(h: str, category: str | None = None) -> list[dict]:
    """Product tiles of a subway.com/de-AT menu category page → dicts (id, name, description, image_url, url, category)."""
    out, seen = [], set()
    for m in TILE_RE.finditer(h):
        pid, href, attrs, name = m.group(1), _html.unescape(m.group(2)), m.group(3), _html.unescape(re.sub(r"<[^>]+>", "", m.group(4))).strip()
        if pid in seen: continue
        seen.add(pid)
        src = _a(attrs, "src")
        out.append({"id": pid, "name": name, "description": _a(attrs, "title") or None,
                    "image_url": (BASE + src if src and src.startswith("/") else src),
                    "url": BASE + href if href.startswith("/") else href, "category": category,
                    "generic_tile": name.strip().lower() in GENERIC})
    return out

def norm(name: str) -> str:
    """'Italian B.M.T.®' / 'Smokey Beast' / "Chick 'N' Garlic" → comparable key (PDF spelling differences)."""
    n = _html.unescape(name).lower().replace("®", "").replace("™", "").replace("smokey", "smoky")
    return re.sub(r"[^a-z0-9äöüß]+", "", n)

def to_product(t: dict) -> Product:
    return Product(source="subway-at", store=STORE, name=t["name"], brand="Subway", price_eur=None,
        image_url=None if t["generic_tile"] else t["image_url"], category=CATEGORIES.get(t["category"] or "", t["category"]),
        source_url=t["url"], source_id=t["id"],
        extra={"description": t["description"], "tile_image_url": t["image_url"], "generic_tile": t["generic_tile"],
               "menu_category": t["category"], "price_note": "subway.com/de-AT veröffentlicht keine Preise (Franchise)",
               "nutrition_note": "Nährwerte nur im AT-Nährwert-PDF von subway.com (nicht in den Menü-Kacheln)"})

class SubwayAT(Adapter):
    id = "subway-at"; store = STORE; homepage = BASE + "/de-AT"; status = "live"
    notes = ("Live: subway.com/de-AT menu category pages (server-rendered tiles; robots disallows only /sitecore/ + "
             "non-AT deliverylocator; polite 1 req/s). Name, description, official tile photo, category, Subway "
             "ProductId. No prices on the AT site; nutrition only in the AT PDF. Generic group tiles are flagged.")
    def tiles(self, category: str) -> list[dict]:
        return parse_tiles(get(MENU + category, raw=True, timeout=60).decode("utf-8", "replace"), category)
    def menu(self, categories=None) -> list[dict]:
        out, seen = [], set()
        for c in categories or CATEGORIES:
            for t in self.tiles(c):
                if t["id"] in seen: continue
                seen.add(t["id"]); out.append(t)
        return out
    def search(self, q: str, limit: int = 20) -> list[Product]:
        words = re.findall(r"\w{3,}", q.lower())
        return [to_product(t) for t in self.menu() if all(w in t["name"].lower() for w in words)][:limit]
    def fetch(self, category: str = "ready-meals", limit: int = 200) -> list[Product]:
        cats = MEAL_CATS if category == "ready-meals" else ([category] if category in CATEGORIES else list(CATEGORIES))
        return [to_product(t) for t in self.menu(cats) if not t["generic_tile"]][:limit]
