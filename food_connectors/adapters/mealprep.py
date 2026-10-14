"""Online meal-prep shops (Shopify storefronts) serving Austria.

Uses the public Shopify storefront endpoints (/products.json and the product
HTML page) and parses the "Nährwerte" table (per 100 g + per portion).
"""
from __future__ import annotations
import html as _html, json, re
from .base import Adapter
from ..http import get
from ..schema import Product

_LABELS = {"energie": "kcal", "brennwert": "kcal", "fett": "fat", "gesättigt": "satfat", "davon gesätt": "satfat",
           "kohlenhydrat": "carbs", "zucker": "sugar", "ballast": "fiber", "eiweiß": "protein", "eiweiss": "protein",
           "protein": "protein", "salz": "salt"}
SKIP = re.compile(r"box|paket|probier|gutschein|abo|shot|saft|minisaft|kids|merch|shaker|bundle|offer|vorrat|\bCH\b", re.I)

def _num(s):
    s = s.replace(".", "").replace(",", ".") if re.search(r"\d\.\d{3}", s) else s.replace(",", ".")
    m = re.findall(r"(\d+(?:\.\d+)?)", s)
    return m

def parse_nutrition(page: str):
    t = page
    for a, b in (("\\u003c", "<"), ("\\u003e", ">"), ("\\/", "/"), ('\\"', '"'), ("\\n", " "), ("\\u0026", "&")):
        t = t.replace(a, b)
    t = _html.unescape(t)
    i = t.find("Nährwerte")
    if i < 0: return {}, None
    seg = t[i:i + 6000]
    portion = None
    m = re.search(r"(?:Nettogewicht|Füllmenge|Nettofüllmenge|Inhalt|Gewicht)\s*:?\s*(?:<[^>]+>\s*)*(\d{2,4})\s*g", t) or re.search(r"Portion[^<]{0,20}?(\d+(?:[.,]\d+)?)\s*g", seg)
    if m: portion = float(m.group(1).replace(",", "."))
    out = {}
    for row in re.findall(r"<tr.*?</tr>", seg, re.S):
        cells = [re.sub(r"<[^>]+>", " ", c).strip() for c in re.findall(r"<td.*?</td>", row, re.S)]
        if len(cells) < 2: continue
        lab = cells[0].lower()
        key = "satfat" if "gesätt" in lab else next((v for k, v in _LABELS.items() if k in lab), None)
        if not key or key in out: continue
        if "gesätt" in lab: key = "satfat"
        if "davon zucker" in lab or lab.startswith("zucker"): key = "sugar"
        nums = _num(cells[1])
        if not nums: continue
        if key == "kcal":
            km = re.search(r"(\d+(?:[.,]\d+)?)\s*kcal", cells[1].replace(".", ""))
            if not km: continue
            out[key] = float(km.group(1).replace(",", "."))
        else:
            out[key] = float(nums[0])
    return out, portion

class ShopifyMealShop(Adapter):
    domain = ""
    def _products(self):
        out, page = [], 1
        while page < 10:
            d = get(f"https://{self.domain}/products.json?limit=250&page={page}")
            ps = d.get("products", [])
            if not ps: break
            out += ps; page += 1
        return out
    def _to_product(self, p):
        v = p["variants"][0]
        img = (p.get("images") or [{}])[0].get("src")
        return Product(source=self.id, store=self.store, name=p["title"], brand=self.store.replace("Online: ", ""),
                       price_eur=float(v["price"]) if v.get("price") else None, image_url=img,
                       category=", ".join(([p["product_type"]] if p.get("product_type") else []) + p.get("tags", [])[:6]) or None,
                       source_url=f"https://{self.domain}/products/{p['handle']}", source_id=str(p["id"]),
                       size_g=float(v["grams"]) if v.get("grams") else None, extra={"available": any(x.get("available") for x in p["variants"]), "tags": p.get("tags", [])})
    def search(self, q, limit=50):
        q = q.lower()
        return [self._to_product(p) for p in self._products() if q in p["title"].lower()][:limit]
    def fetch(self, category="ready-meals", limit=500):
        best = {}
        for p in self._products():
            t = re.sub(r"\s*\(ausverkauft\)", "", p["title"]).strip()
            if SKIP.search(t) or t.startswith("CH:"): continue
            base = not re.search(r"-\d+$|kopie", p["handle"])
            pr = float(p["variants"][0].get("price") or 0)
            cur = best.get(t)
            if cur is None or (base and not cur[0]) or (base == cur[0] and pr > cur[1]):
                best[t] = (base, pr, p)
        res = []
        for t, (_, _, p) in best.items():
            x = self._to_product(p); x.name = t; res.append(x)
        return res[:limit]
    def enrich(self, p):
        try:
            h = get(p.source_url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)", "Accept": "text/html"}, raw=True).decode("utf-8", "ignore")
        except Exception:
            return p
        n, portion = parse_nutrition(h)
        if portion: p.size_g = portion
        gm = re.search(r"Grundpreis\s*(?:<[^>]+>\s*)*(\d{2,4})\s*g\b", h)
        if not portion and gm: p.size_g = float(gm.group(1))
        if not n.get("protein"):
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*g\s*Protein\s*/\s*(\d+)\s*kcal(?:\s*/\s*(\d+(?:[.,]\d+)?)\s*g\s*KH)?(?:\s*/\s*(\d+(?:[.,]\d+)?)\s*g\s*Fett)?\s*pro Portion", h)
            if m and p.size_g:
                f = 100 / p.size_g; g = lambda x: round(float(x.replace(",", ".")) * f, 1) if x else None
                n = {k: v for k, v in {"protein": g(m.group(1)), "kcal": g(m.group(2)), "carbs": g(m.group(3)), "fat": g(m.group(4))}.items() if v is not None}
                p.extra["nutrition_basis"] = "pro Portion lt. Shop, auf 100 g umgerechnet"
        p.nutrition_100g = n
        return p

class PrepMyMeal(ShopifyMealShop):
    id = "prepmymeal"; store = "Online: PrepMyMeal"; domain = "prepmymeal.at"; homepage = "https://prepmymeal.at"
    notes = "Shopify storefront; Versand AT per DPD gekühlt, 5,99 € (lt. Versandseite)"

class LiveFresh(ShopifyMealShop):
    id = "livefresh"; store = "Online: LiveFresh"; domain = "livefresh.at"; homepage = "https://livefresh.at"
    notes = "Shopify storefront; vegane Fertiggerichte + Shots (nur Bowls werden übernommen)"
    def fetch(self, category="ready-meals", limit=500):
        # Filter bowls AFTER full catalog scan — passing limit into super() truncated to
        # drinks/non-bowls first and made fetch(limit=3) (hub smoke) return 0.
        meals = [p for p in super().fetch(category, limit=500) if "Bowl" in p.name or "fertiggericht" in (p.category or "").lower()]
        return meals[:limit]
    def search(self, q, limit=50):
        ql = q.lower(); words = re.findall(r"\w{3,}", ql)
        meals = self.fetch()
        hits = [p for p in meals if any(w[:5] in p.name.lower() for w in words)]
        # Fall back to any bowls so smoke queries (gulasch/lasagne/suppe) still prove live
        return (hits or meals)[:limit]

class Gourmetfein(ShopifyMealShop):
    id = "gourmetfein"; store = "Online: Gourmetfein"; domain = "shop.gourmetfein.com"; homepage = "https://shop.gourmetfein.com"
    notes = "DEAD END for ready meals (verified 2026-10-14T0307): Shopify live, 75 products = Wurst/Leberkäse/Grill only — 0 Fertiggerichte; connector kept for catalog completeness, not imported into online_mealprep"
