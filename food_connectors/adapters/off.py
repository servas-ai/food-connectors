import urllib.parse
from .base import Adapter
from ..http import get
from ..schema import Product, find_producer_id, parse_size_g
N = {"energy-kcal_100g": "kcal", "proteins_100g": "protein", "fat_100g": "fat", "saturated-fat_100g": "satfat", "carbohydrates_100g": "carbs", "sugars_100g": "sugar", "fiber_100g": "fiber", "salt_100g": "salt"}
def from_off(p, store="Open Food Facts"):
    nm = p.get("nutriments") or {}
    return Product(source="off", store=store, name=p.get("product_name_de") or p.get("product_name") or "", brand=p.get("brands"),
        size_g=parse_size_g(p.get("quantity")), nutrition_100g={v: nm[k] for k, v in N.items() if k in nm}, ean=p.get("code"),
        image_url=p.get("image_front_url"), producer=p.get("manufacturing_places") or None,
        producer_id=find_producer_id(p.get("emb_codes")) or p.get("emb_codes") or None, origin=p.get("origins") or None,
        category=p.get("categories"), source_url=f"https://world.openfoodfacts.org/product/{p.get('code')}", source_id=p.get("code"),
        extra={"stores": p.get("stores"), "nutriscore": p.get("nutriscore_grade"), "nova": p.get("nova_group")})
class OpenFoodFacts(Adapter):
    id = "off"; store = "Open Food Facts"; homepage = "https://world.openfoodfacts.org"
    notes = "Open database (ODbL). No prices; good for EAN, nutrition and EMB/Identitätskennzeichen. Filtered to products sold in Austria."
    def search(self, q, limit=50):
        d = get("https://world.openfoodfacts.org/cgi/search.pl?" + urllib.parse.urlencode({"search_terms": q, "countries_tags_en": "austria", "json": 1, "page_size": min(limit, 100)}), timeout=60)
        return [from_off(p) for p in d.get("products", [])]
    def by_ean(self, ean):
        d = get(f"https://world.openfoodfacts.org/api/v2/product/{ean}.json")
        return from_off(d["product"]) if d.get("status") == 1 else None
