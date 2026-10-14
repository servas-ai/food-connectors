"""Juit (juit.com) — frozen ready meals shipped to Austria (DHL Express, weekly).

Source: the public content bundle the juit.com storefront itself loads,
``https://cdn.juit.gmbh/content-de.json`` (Contentful export: entries + assets;
juit.com robots.txt only disallows /order, /profile, /checkout, /thankyou).
Every ``dish`` entry carries title, slug, EAN, net weight, portions, the full
nutrition table per 100 g, ingredients, tags and the official packshot asset.

Prices are NOT in the public bundle: api.juitnow.com price lists answer 401
(authentication required), so ``price_eur`` stays None — never guessed.
``sellable`` (currently orderable) is kept in ``extra``; fetch() returns only
sellable dishes unless ``include_unsellable=True``.
Operator: Juit GmbH, Lutterstraße 14, 33617 Bielefeld (DE), HRB 42921 AG Bielefeld,
USt-ID DE316648632 (public Impressum in the same bundle).
"""
from __future__ import annotations
import re
from .base import Adapter
from ..http import get
from ..schema import Product

CONTENT_URL = "https://cdn.juit.gmbh/content-{lang}.json"
DISH_URL = "https://www.juit.com/{lang}/gerichte/{slug}"
_NUT = {"energy": "kcal", "protein": "protein", "fat": "fat", "saturatedFat": "satfat", "carbohydrate": "carbs",
        "sugar": "sugar", "fiber": "fiber", "salt": "salt"}

def _text(node) -> str:
    """Flatten a Contentful rich-text document to plain text."""
    if not isinstance(node, dict): return ""
    if node.get("nodeType") == "text": return node.get("value", "")
    sep = "\n" if node.get("nodeType") in ("document", "unordered-list", "ordered-list") else ""
    return sep.join(_text(c) for c in node.get("content", [])).strip()

def content(lang: str = "de") -> dict:
    return get(CONTENT_URL.format(lang=lang), timeout=60)

def dishes(lang: str = "de", data: dict | None = None) -> list[dict]:
    d = data or content(lang)
    assets = {a["sys"]["id"]: a for a in d.get("assets", [])}
    out = []
    for e in d.get("entries", []):
        if e["sys"].get("contentType", {}).get("sys", {}).get("id") != "dish": continue
        f = dict(e["fields"])
        img = (f.get("image") or {}).get("sys", {}).get("id")
        f["_image_url"] = ((assets.get(img) or {}).get("fields", {}).get("file") or {}).get("url")
        f["_id"] = e["sys"]["id"]
        out.append(f)
    return out

def to_product(f: dict, lang: str = "de") -> Product:
    slug = f.get(f"slug_{lang}") or f.get("slug")
    n = {v: float(f[k]) for k, v in _NUT.items() if isinstance(f.get(k), (int, float))}
    tags = list(f.get("dishTags") or [])
    return Product(source="juit", store="Online: Juit", name=(f.get("title") or "").strip(), brand="Juit",
                   price_eur=None, size_g=float(f["weight"]) if f.get("weight") else None, nutrition_100g=n,
                   ean=str(f["ean"]) if f.get("ean") else None, image_url=f.get("_image_url"),
                   producer="Juit GmbH, Bielefeld (DE)", category=", ".join(["Online Meal-Prep"] + tags[:6]),
                   source_url=DISH_URL.format(lang=lang, slug=slug) if slug else None, source_id=f.get("_id"),
                   extra={"sellable": bool(f.get("sellable")), "portions": f.get("portions"), "tags": tags,
                          "categories": f.get("dishCategories") or [], "special_tag": f.get("specialTag"),
                          "ingredients": _text(f.get("ingredients")) or None, "more_info": f.get("moreInfo"),
                          "microwave": {"watts": f.get("microwave_watts"), "minutes": f.get("microwave_time_in_minutes")},
                          "price_note": "Einzelpreise nicht öffentlich (api.juitnow.com Preislisten 401) — nicht geschätzt"})

def is_ready_meal(p: Product) -> bool:
    return not re.search(r"gutschein|box\b|bundle|getränk|drink|dessert", p.name, re.I)

class Juit(Adapter):
    id = "juit"; store = "Online: Juit"; homepage = "https://www.juit.com/de"
    notes = ("Live: public storefront content bundle cdn.juit.gmbh/content-de.json (dish entries: EAN, weight, nutrition/100 g, "
             "ingredients, packshot); AT delivery weekly via DHL Express; prices need login (401) → price None")
    def fetch(self, category="ready-meals", limit=500, include_unsellable=False):
        ps = [to_product(f) for f in dishes()]
        ps = [p for p in ps if p.name and is_ready_meal(p) and (include_unsellable or p.extra["sellable"])]
        return ps[:limit]
    def search(self, q, limit=50):
        words = re.findall(r"\w{3,}", q.lower())
        meals = [to_product(f) for f in dishes()]
        hits = [p for p in meals if all(w in f"{p.name} {p.category}".lower() for w in words)]
        return hits[:limit]
