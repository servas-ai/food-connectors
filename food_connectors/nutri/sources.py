import csv, io, os, re, urllib.parse, zipfile
from ..http import get
CACHE = os.path.expanduser(os.environ.get("FOOD_CACHE", "~/.cache/food-connectors"))
def _norm_off(p):
    nm = p.get("nutriments") or {}
    g = (p.get("nutriscore_grade") or "").upper()
    return {"source": "off", "ean": p.get("code"), "name": p.get("product_name_de") or p.get("product_name"), "brand": p.get("brands"),
        "nutriscore": g if g in "ABCDE" and g else None, "nutriscore_status": "offiziell (OFF)" if g in ("A","B","C","D","E") else None,
        "nutriscore_score": p.get("nutriscore_score"), "nova": p.get("nova_group"),
        "ecoscore": (p.get("ecoscore_grade") or "").upper() or None, "additives": [a.split(":")[-1].upper() for a in p.get("additives_tags") or []],
        "ingredients_analysis": p.get("ingredients_analysis_tags") or [], "fvl_pct": nm.get("fruits-vegetables-legumes-estimate-from-ingredients_100g") or nm.get("fruits-vegetables-nuts-estimate-from-ingredients_100g"),
        "nutrition_100g": {k: nm.get(f) for k, f in [("kcal","energy-kcal_100g"),("protein","proteins_100g"),("fat","fat_100g"),("satfat","saturated-fat_100g"),("carbs","carbohydrates_100g"),("sugar","sugars_100g"),("fiber","fiber_100g"),("salt","salt_100g")]},
        "countries": p.get("countries_tags"), "url": f"https://world.openfoodfacts.org/product/{p.get('code')}"}
OFF_FIELDS = "code,product_name,product_name_de,brands,nutriscore_grade,nutriscore_score,nova_group,ecoscore_grade,additives_tags,ingredients_analysis_tags,nutriments,countries_tags"
class OFFNutri:
    id = "off-nutri"; name = "Open Food Facts (Nutri-Score/NOVA/Eco-Score/Zusatzstoffe)"; license = "ODbL"; status = "live"
    url = "https://world.openfoodfacts.org/api/v2"; dumps = "https://static.openfoodfacts.org/data/openfoodfacts-products.jsonl.gz (nightly); Parquet: huggingface.co/datasets/openfoodfacts/product-database"
    def by_ean(self, ean):
        d = get(f"https://world.openfoodfacts.org/api/v2/product/{ean}.json?fields={OFF_FIELDS}")
        return _norm_off(d["product"]) if d.get("status") == 1 else None
    def search(self, q, limit=10, country="austria"):
        params = {"search_terms": q, "json": 1, "page_size": limit, "fields": OFF_FIELDS}
        if country: params["countries_tags_en"] = country
        d = get("https://world.openfoodfacts.org/cgi/search.pl?" + urllib.parse.urlencode(params), timeout=60)
        return [_norm_off(p) for p in d.get("products", [])]
class USDA:
    id = "usda-fdc"; name = "USDA FoodData Central"; license = "CC0"; status = "live"; url = "https://api.nal.usda.gov/fdc/v1"
    M = {1008: "kcal", 1003: "protein", 1004: "fat", 1258: "satfat", 1005: "carbs", 2000: "sugar", 1079: "fiber", 1093: "sodium_mg"}
    def search(self, q, limit=10):
        key = os.environ.get("FDC_API_KEY", "DEMO_KEY")
        d = get(f"{self.url}/foods/search?" + urllib.parse.urlencode({"query": q, "pageSize": limit, "api_key": key}))
        out = []
        for f in d.get("foods", []):
            n = {self.M[x["nutrientId"]]: x.get("value") for x in f.get("foodNutrients", []) if x.get("nutrientId") in self.M}
            if "sodium_mg" in n: n["salt"] = round(n.pop("sodium_mg") * 2.5 / 1000, 2)
            out.append({"source": self.id, "fdc_id": f.get("fdcId"), "ean": f.get("gtinUpc"), "name": f.get("description"), "brand": f.get("brandOwner"), "data_type": f.get("dataType"), "nutrition_100g": n})
        return out
    by_ean = lambda self, ean: (self.search(ean, 3) or [None])[0]
class CIQUAL:
    id = "ciqual"; name = "ANSES CIQUAL 2020 (generische Lebensmittel, FR)"; license = "Etalab Open Licence"; status = "live (CSV/XLSX download)"
    url = "https://ciqual.anses.fr/"; data = "https://www.data.gouv.fr/fr/datasets/table-de-composition-nutritionnelle-des-aliments-ciqual/"
    def search(self, q, limit=10):
        return [{"source": self.id, "hint": "Download table from data.gouv.fr, then: food nutri --ciqual-file <csv>", "url": self.data}]
class Catalog:
    def __init__(s, i, n, u, lic, note): s.id, s.name, s.url, s.license, s.notes, s.status = i, n, u, lic, note, "catalog-only"
    def search(self, q, limit=10): return []
NUTRI_SOURCES = {a.id: a for a in [OFFNutri(), USDA(), CIQUAL(),
    Catalog("opf", "Open Products Facts", "https://world.openproductsfacts.org", "ODbL", "Non-food; n/a for nutrition."),
    Catalog("off-at", "Open Food Facts Austria subset", "https://at.openfoodfacts.org", "ODbL", "Use off-nutri with country=austria or filter nightly dump on countries_tags=en:austria."),
    Catalog("bls", "Bundeslebensmittelschlüssel BLS 4.0 (MRI)", "https://www.blsdb.de", "Free download after registration (BLS 4.0, 2025)", "~7.000 generic foods; licence forbids redistribution of raw table -> not bundled."),
    Catalog("oenwt", "Österreichische Nährwerttabelle", "https://www.oenwt.at", "proprietary web", "Web lookup only, no API/bulk download; not scraped."),
    Catalog("swiss-fcdb", "Schweizer Nährwertdatenbank (BLV)", "https://naehrwertdaten.ch/de/downloads/", "free download (XLSX)", "Generic foods, XLSX download; usable for ingredient-level fallback."),
    Catalog("efsa-openfoodtox", "EFSA OpenFoodTox", "https://zenodo.org/communities/efsa-kj", "CC-BY 4.0", "Toxicology reference values (ADI) per substance; join with additive E-numbers."),
    Catalog("codecheck", "codecheck.at", "https://www.codecheck.info", "proprietary", "No public API; ToS forbid scraping -> not used."),
]}
def nutri_lookup(q, sources=("off-nutri",)):
    out = []
    for s in sources:
        a = NUTRI_SOURCES[s]
        if q.isdigit() and hasattr(a, "by_ean"):
            r = a.by_ean(q); out += [r] if r else []
        else: out += a.search(q, 5)
    return out
