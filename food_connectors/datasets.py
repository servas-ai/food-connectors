"""Open dataset catalog + live search on Hugging Face, Zenodo, data.gv.at, Kaggle (public APIs, no auth)."""
import urllib.parse as up
from .http import get

CATALOG = [
 {"id": "off-hf", "name": "Open Food Facts product-database (Parquet)", "url": "https://huggingface.co/datasets/openfoodfacts/product-database", "license": "ODbL (DB) / DbCL (contents)", "size": "~4M products, several GB", "freshness": "daily", "use": "EAN, Nährwerte, Nutri-Score, NOVA; live via `food search --store off` / `food nutri`"},
 {"id": "off-kaggle", "name": "Open Food Facts world-food-facts (Kaggle)", "url": "https://www.kaggle.com/datasets/openfoodfacts/world-food-facts", "license": "ODbL", "size": "114 MB", "freshness": "stale (2017 snapshot)", "use": "historical only, prefer off-hf"},
 {"id": "heisse-preise", "name": "heisse-preise.io daily dump (badlogic/heissepreise, MIT)", "url": "https://heisse-preise.io/data/latest-canonical.json", "license": "code MIT; prices = retailer data", "size": "~200 MB JSON", "freshness": "daily", "use": "AT prices Billa/Spar/Hofer/Lidl/Penny/dm/MPreis/Unimarkt; live via `--store heisse-preise`"},
 {"id": "heisse-preise-data", "name": "falknerdominik/heisse-preise-data", "url": "https://github.com/falknerdominik/heisse-preise-data", "license": "MIT", "size": "Python loader", "freshness": "pushed 2026-10-12", "use": "price history loader for heisse-preise"},
 {"id": "ciqual", "name": "ANSES CIQUAL 2020", "url": "https://ciqual.anses.fr", "license": "Etalab Open Licence 2.0", "size": "3,185 foods", "freshness": "2020", "use": "generic composition; `food nutri --sources ciqual`"},
 {"id": "usda-fdc", "name": "USDA FoodData Central", "url": "https://fdc.nal.usda.gov", "license": "CC0", "size": "~400k foods", "freshness": "semi-annual 2026", "use": "`food nutri --sources usda-fdc` (DEMO_KEY or FDC_API_KEY)"},
 {"id": "swiss-fcdb", "name": "Swiss Food Composition Database (BLV)", "url": "https://naehrwertdaten.ch", "license": "free use with attribution (BLV terms)", "size": "~1,100 generic foods", "freshness": "V7.0 (2024+)", "use": "catalog; Excel download"},
 {"id": "bls", "name": "Bundeslebensmittelschlüssel BLS 4.0 (MRI)", "url": "https://blsdb.de", "license": "free since BLS 4.0 (CC BY 4.0 per MRI)", "size": "~7,100 foods", "freshness": "2025", "use": "catalog; download manually from blsdb.de"},
 {"id": "zenodo-nl", "name": "Dutch supermarket product data (Zenodo 10.5281/zenodo.19220002)", "url": "https://doi.org/10.5281/zenodo.19220002", "license": "CC BY 4.0", "size": "see record", "freshness": "2026-03", "use": "reference schema, not AT"},
 {"id": "kaggle-de-retail", "name": "German retail supermarket dataset (Kaggle sanku758)", "url": "https://www.kaggle.com/datasets/sanku758/german-retail-supermarket-dataset", "license": "MIT (stated)", "size": "1.95 GB", "freshness": "unknown, likely synthetic", "use": "not imported (provenance unclear)"},
 {"id": "data-gv-lebensmittelbuch", "name": "Österreichisches Lebensmittelbuch (data.gv.at)", "url": "https://www.data.gv.at/katalog/?q=lebensmittelbuch", "license": "CC BY 4.0", "size": "PDF/HTML chapters", "freshness": "2021", "use": "legal definitions (Codex B?), no products"},
 {"id": "open-prices", "name": "Open Prices (Open Food Facts) — crowd-sourced receipt/price-tag observations", "url": "https://prices.openfoodfacts.org", "license": "ODbL 1.0", "size": "daily dump on Hugging Face (openfoodfacts/open-prices); REST API per EAN", "freshness": "continuous (user contributions)", "use": "dated, OSM-located price observations by EAN; live via `food prices EAN --country AT` / MCP `open_prices_lookup`; AT coverage sparse (2026-10-16: 7 of 240 non-live dataset EANs had any observation, none AT 2026)"},
]

def search(q, hubs=("hf", "zenodo", "datagv", "kaggle"), n=8):
    out, errors = [], {}
    qq = up.quote(q)
    for h in hubs:
        try:
            if h == "hf":
                for d in get(f"https://huggingface.co/api/datasets?search={qq}&limit={n}"):
                    out.append({"hub": "huggingface", "id": d["id"], "url": "https://huggingface.co/datasets/" + d["id"], "updated": (d.get("lastModified") or "")[:10], "downloads": d.get("downloads"), "license": next((t[8:] for t in d.get("tags", []) if t.startswith("license:")), None)})
            elif h == "zenodo":
                for r in get(f"https://zenodo.org/api/records?q={qq}&size={n}")["hits"]["hits"]:
                    m = r["metadata"]; out.append({"hub": "zenodo", "id": r.get("doi"), "title": m.get("title"), "url": r["links"].get("self_html"), "updated": r.get("updated", "")[:10], "license": (m.get("license") or {}).get("id"), "size_bytes": sum(f.get("size", 0) for f in r.get("files", []))})
            elif h == "datagv":
                for r in get(f"https://www.data.gv.at/api/hub/search/search?q={qq}&filter=dataset&limit={n}")["result"]["results"]:
                    out.append({"hub": "data.gv.at", "id": r.get("id"), "title": (r.get("title") or {}).get("de"), "url": "https://www.data.gv.at/katalog/datasets/" + str(r.get("id")), "updated": (r.get("modified") or "")[:10]})
            elif h == "kaggle":
                for d in get(f"https://www.kaggle.com/api/v1/datasets/list?search={qq}")[:n]:
                    out.append({"hub": "kaggle", "id": d.get("refNullable") or d.get("urlNullable"), "title": d.get("titleNullable"), "url": d.get("urlNullable"), "license": d.get("licenseNameNullable"), "size_bytes": d.get("totalBytesNullable")})
        except Exception as e:
            errors[h] = repr(e)[:200]
    return {"results": out, "errors": errors}
