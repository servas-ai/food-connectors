import urllib.parse
from .base import Adapter
from ..http import get
from ..schema import Product, find_producer_id, parse_size_g
KEYS = {"energyKCal": "kcal", "protein": "protein", "fats": "fat", "saturatedFats": "satfat", "carbohydrates": "carbs", "sugars": "sugar", "fiber": "fiber", "salt": "salt"}
B = "https://www.gurkerl.at"

class Gurkerl(Adapter):
    id = "gurkerl"; store = "Gurkerl.at"; homepage = B
    notes = "Online supermarket (Rohlik group), delivers to Linz. Public frontend JSON: search-metadata, /api/v1/products/{id}/details|composition|prices."
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
    def enrich(self, p):
        try:
            c = get(f"{B}/api/v1/products/{p.source_id}/composition")
            nv = (c.get("nutritionalValues") or [{}])[0].get("values") or {}
            p.nutrition_100g = {KEYS[k]: v["amount"] for k, v in nv.items() if k in KEYS and v}
            ing = c.get("plainIngredients") or ""
            p.extra["ingredients"] = ing[:2000]
            for line in ing.splitlines():
                if line.lower().startswith(("produzent", "hersteller", "inverkehrbringer", "kontakt", "vertrieb")):
                    p.producer = line.split(":", 1)[-1].strip(); break
            p.producer_id = find_producer_id(ing)
            d = get(f"{B}/api/v1/products/{p.source_id}/details")["product"]
            p.origin = ", ".join(c["name"] for c in d.get("countries") or []) or None
        except Exception:
            pass
        return p
