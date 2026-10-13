import urllib.parse
from .base import Adapter
from ..http import get
from ..schema import Product, find_producer_id, parse_size_g
KEYS = {"energyKCal": "kcal", "protein": "protein", "fats": "fat", "saturatedFats": "satfat", "carbohydrates": "carbs", "sugars": "sugar", "fiber": "fiber", "salt": "salt"}
B = "https://www.gurkerl.at"
# Ready-meal categories (ids from /api/v1/categories/normal/{id}[/subcategories]); verified 2026-10-13
MEAL_CATEGORIES = {
    135049: "Kühlregal > Schnelle Küche > Fertiggerichte > Traditionelle Hausmannskost",
    135050: "Kühlregal > Schnelle Küche > Fertiggerichte > Asiatisch- / Orientalische Küche",
    135051: "Kühlregal > Schnelle Küche > Fertiggerichte > Mediterrane Köstlichkeiten",
    134260: "Kühlregal > Schnelle Küche > Suppen & Fonds",
    602: "Tiefkühlprodukte > Fertiggerichte",
    136143: "Tiefkühlprodukte > Mehlspeisen > Warme Mehlspeisen & Süße Knödel",
    312: "Vorratsschrank > Fertiggerichte",
    380: "Vorratsschrank > Fertiggerichte > Menüs & Dosengerichte",
    379: "Vorratsschrank > Fertiggerichte > Suppen",
    906: "Marks & Spencer > Fertiggerichte",
    620: "Tiefkühlprodukte > Pizza, Baguettes & Flammkuchen > Pizza",  # added 2026-10-13T11
}

def parse_composition(c):
    """composition JSON -> (nutrition_100g, ingredients, producer, producer_id, ean)"""
    nv = (c.get("nutritionalValues") or [{}])[0].get("values") or {}
    n = {KEYS[k]: v["amount"] for k, v in nv.items() if k in KEYS and v and v.get("amount") is not None}
    ing = c.get("plainIngredients") or ""
    prod = None
    for line in ing.splitlines():
        if line.lower().startswith(("produzent", "hersteller", "inverkehrbringer", "kontakt", "vertrieb")):
            prod = line.split(":", 1)[-1].strip(); break
    return n, ing, prod, find_producer_id(ing), (str(c["ean"]) if c.get("ean") else None)

class Gurkerl(Adapter):
    id = "gurkerl"; store = "Gurkerl.at"; homepage = B
    notes = "Online supermarket (Rohlik group), delivers to Linz. Public frontend JSON: search-metadata, /api/v1/categories/normal/{id}/products, /api/v1/products?products=, /api/v1/products/{id}/details|composition|prices."
    def search(self, q, limit=50):
        d = get(f"{B}/services/frontend-service/search-metadata?" + urllib.parse.urlencode({"search": q, "offset": 0, "limit": min(limit, 100), "companyId": 1}))["data"]
        out = []
        for r in d.get("productList", []):
            cats = r.get("categories") or []
            out.append(Product(source=self.id, store=self.store, name=r["productName"], brand=r.get("brand"),
                price_eur=(r.get("price") or {}).get("full"), unit_price_eur=(r.get("pricePerUnit") or {}).get("full"), unit=r.get("unit"),
                size_g=parse_size_g(r.get("textualAmount")), image_url="https://cdn.gurkerl.at" + r["imgPath"] if r.get("imgPath") else None,
                category=" > ".join(c["name"] for c in sorted(cats, key=lambda c: c.get("level", 0))),
                source_url=f"{B}/{r.get('baseLink')}", source_id=str(r["productId"])))
        return out
    def category_ids(self, cat_id, limit=500):
        """All product ids of a category (walks subcategories)."""
        ids = list(get(f"{B}/api/v1/categories/normal/{cat_id}/products?offset=0&limit={limit}").get("productIds") or [])
        for sub in get(f"{B}/api/v1/categories/normal/{cat_id}/subcategories").get("categoryIds") or []:
            ids += [i for i in self.category_ids(sub, limit) if i not in ids]
        return ids
    def products(self, ids, category=None):
        """Batch product cards + prices + stock (in_stock in extra)."""
        out = []
        for i in range(0, len(ids), 40):
            chunk = ids[i:i + 40]; qs = "&".join(f"products={x}" for x in chunk)
            cards = get(f"{B}/api/v1/products?{qs}"); prices = {p["productId"]: p for p in get(f"{B}/api/v1/products/prices?{qs}")}
            stock = {s["productId"]: s for s in get(f"{B}/api/v1/products/stock?{qs}")}
            for c in cards:
                pr = prices.get(c["id"]) or {}; st = stock.get(c["id"]) or {}
                out.append(Product(source=self.id, store=self.store, name=c["name"].strip(), brand=c.get("brand"),
                    price_eur=(pr.get("price") or {}).get("amount"), unit_price_eur=(pr.get("pricePerUnit") or {}).get("amount"), unit=c.get("unit"),
                    size_g=parse_size_g(c.get("textualAmount")), image_url=(c.get("images") or [None])[0], category=category,
                    origin=", ".join(x["name"] for x in c.get("countries") or []) or None,
                    source_url=f"{B}/{c['id']}-{c['slug']}", source_id=str(c["id"]),
                    extra={"in_stock": st.get("inStock"), "archived": c.get("archived")}))
        return out
    def fetch(self, category="ready-meals", limit=2000):
        if category != "ready-meals": return super().fetch(category, limit)
        seen, out = set(), []
        for cid, label in MEAL_CATEGORIES.items():
            try: ids = [i for i in self.category_ids(cid) if i not in seen]
            except Exception: continue
            seen.update(ids)
            out += [p for p in self.products(ids, label) if not p.extra.get("archived")]
        return out[:limit]
    def enrich(self, p):
        try:
            n, ing, prod, pid, ean = parse_composition(get(f"{B}/api/v1/products/{p.source_id}/composition"))
            p.nutrition_100g = n or p.nutrition_100g
            p.extra["ingredients"] = ing[:2000]
            p.producer = prod or p.producer; p.producer_id = pid or p.producer_id; p.ean = ean or p.ean
            if not p.origin:
                d = get(f"{B}/api/v1/products/{p.source_id}/details")["product"]
                p.origin = ", ".join(c["name"] for c in d.get("countries") or []) or None
        except Exception:
            pass
        return p
