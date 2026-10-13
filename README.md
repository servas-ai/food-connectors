# food-connectors 🥘🇦🇹

Open, dependency-free (Python ≥ 3.9, stdlib only) connectors, CLI and **MCP server** for Austrian grocery and ready-meal (Fertiggerichte) data.
Every adapter returns the same schema:

| field | meaning |
|---|---|
| `name`, `brand`, `store`, `category` | product identity |
| `price_eur`, `unit_price_eur`, `unit`, `size_g` | price, unit price (per `unit`), pack size in g/ml |
| `nutrition_100g` | `kcal, protein, fat, satfat, carbs, sugar, fiber, salt` |
| `ean`, `image_url` | GTIN and image |
| `producer`, `producer_id` | manufacturer + Identitätskennzeichen (e.g. `AT 40047 EG`) |
| `origin`, `source`, `source_id`, `source_url`, `fetched_at` | provenance |

## Connector status (live test 2026-10-13, `python3 tests/live_status.py` → `status.json`)

| connector | source | live test | reuses / credits |
|---|---|---|---|
| `billa` | shop.billa.at product-discovery API (`term=`) | ✅ pass (fetch via meal search stems; category path 404) | — |
| `penny` | penny.at, same REWE API | ✅ pass | — |
| `gurkerl` | gurkerl.at API | ✅ pass | idea from [pasogott/gurkerlcli](https://github.com/pasogott/gurkerlcli) (MIT), [tomaspavlin/rohlik-mcp](https://github.com/tomaspavlin/rohlik-mcp) (MIT) |
| `lidl` | lidl.at `q/api/search` | ❌ fail – 401 for Python clients (TLS/bot fingerprinting, curl gets 200). Not bypassed by policy; fetchsize capped at 30. Use `heisse-preise` for Lidl prices | — |
| `spar` | interspar via heisse-preise + CDN images (`cdn1.interspar.at` from article id) | ✅ pass (prices + images) | [badlogic/heissepreise](https://github.com/badlogic/heissepreise) (MIT) |
| `spar-shop` | SPAR public product search API `search-spar.spar-ics.com/fact-finder/rest/v4/search/products_lmos_at` (JSON index behind the interspar.at shop; no robots.txt on host, no login/cookies; interspar.at HTML never requested). Exact lookup by article number (`interspar.at/p/<id>`), CLI `food search … --store spar-shop`, MCP `spar_product` | ✅ live (current + regular price, €/kg, brand, category, stock status, CDN image; `code-internal` is a SPAR-internal 88… code, not a GTIN; no nutrition) | SPAR Österreich; endpoint as used by [badlogic/heissepreise](https://github.com/badlogic/heissepreise) (MIT) |
| `denns` | denn's BioMarkt AT public offer feed `denns-biomarkt.at/page-data/angebote/page-data.json` (Gatsby page-data the site itself loads; robots `Allow: /`, no login/cookies). CLI `food fetch --store denns` / `food search … --store denns`, MCP `denns_offers` | ✅ live (weekly offers only: article no., brand, pack, Aktionspreis + Normalpreis, €/kg, validity, vegan flags, official image images.dennree.de; no GTIN/nutrition → `off`) | denn's Biomarkt GmbH |
| `penny-shop` | penny.at public online-assortment JSON `www.penny.at/api/product-discovery/products` (+ `/products/<sku>`) — the calls the penny.at shop itself makes (REWE product-discovery API; robots.txt has only a Sitemap line, no login/cookies; heisse-preise's older `/api/products` path is disabled since 10/2025). CLI `food fetch --store penny-shop` / `food search … --store penny-shop`, MCP `penny_product`, `penny_search` | ✅ live (~450 items incl. weekly offers: regular + standard price, promo text/validity, €/unit, pack, category path, origin, official image; 27 ready-meal candidates 2026-10-13; no GTIN/nutrition → identical BILLA article `00-<no.>` or `off`) | REWE International; endpoint lineage [badlogic/heissepreise](https://github.com/badlogic/heissepreise) (MIT) |
| `nah-frisch` | Nah&Frisch public weekly offers page `nahundfrisch.at/de/aktuelles/angebote-der-woche` (server-rendered HTML, robots `Allow: /`; tiles from `/media/…`, robots-disallowed `/images` `/storage` never requested; no login/cookies). One tab per KW with validity; each offer is an image tile → names/pack/price via local **tesseract OCR** (`extra.ocr`, raw text kept — verify before use). CLI `food fetch --store nah-frisch`, MCP `nahfrisch_offers` | ✅ live (weekly offers only, ~36 tiles/2 weeks: brand+name, pack text, offer price, badge e.g. '1+1 gratis'/'25% billiger', validity, official tile image; no GTIN/nutrition; offers only in participating franchise markets; OCR price 25/26 correct on 2026-10-13) | ZEV Nah&Frisch Marketingservice GmbH; OCR via [tesseract-ocr](https://github.com/tesseract-ocr/tesseract) (Apache-2.0, optional system binary) |
| `mpreis-shop` | mpreis.at webshop: product sitemaps + category pages + product JSON-LD (robots-allowed; `/search/` never used) | ✅ live (price, GTIN, image, nutrition, ingredients) | MPreis Warenvertriebs GmbH |
| `dm` | dm.at product sitemap + public `products.dm.de` product JSON (no login/cookies; `/search` robots-disallowed, never used) | ✅ live (price, GTIN, nutrition, ingredients, origin, non-AI image) | dm-drogerie markt |
| `hofer`, `dm-heisse`, `mpreis`, `unimarkt` | heisse-preise.io daily dump | ✅ pass (prices up to 1 day old) | badlogic/heissepreise |
| `heisse-preise` | heisse-preise.io dump | ✅ pass | badlogic/heissepreise, [falknerdominik/heisse-preise-data](https://github.com/falknerdominik/heisse-preise-data) |
| `off` | Open Food Facts search | ⚠️ flaky – upstream search sometimes returns 503 | [openfoodfacts-python](https://github.com/openfoodfacts/openfoodfacts-python) (API conventions) |
| `prepmymeal`, `gourmetfein` | Shopify `/products.json` | ✅ pass | — |
| `livefresh` | Shopify `/products.json` | ✅ pass (fixed: meals now by `product_type=Fertiggerichte`, search by stem) | — |
| `nutri:off-nutri` | OFF product API v2 (Nutri-Score/NOVA/Eco-Score) | ✅ pass | openfoodfacts-python |
| `nutri:usda-fdc` | USDA FoodData Central API | ✅ pass | API pattern of [Nelson-Gon/pyfdc](https://github.com/Nelson-Gon/pyfdc) (MIT) |
| `nutri:ciqual` | ANSES CIQUAL | ✅ pass | [plemio/ciqual-mcp](https://github.com/plemio/ciqual-mcp) (MIT) |
| `company:gleif` | GLEIF LEI API (AT Firmenbuchnummer, parents) | ✅ pass | [ggravlingen/pygleif](https://github.com/ggravlingen/pygleif) (MIT) |
| `company:vies` | EU VIES UID check | ✅ pass | — |
| `company:northdata` | North Data public page / API key | ✅ pass (public facts only) | [p-meier/northdata-connectors](https://github.com/p-meier/northdata-connectors) |
| `company:impressum` | Public legal notice (Impressum/Imprint: FN, HRB, UID; robots.txt respected) + every UID verified live via EU VIES | ✅ pass (`food company NAME --impressum DOMAIN`, MCP `company_impressum`) | — |
| `company:firmenbuch` | Firmenbuch HVD API (justiz.gv.at) | 🔑 needs free API key `FIRMENBUCH_API_KEY` | [Lukhers-dev/firmenbuch-HVD](https://github.com/Lukhers-dev/firmenbuch-HVD) (MIT) |
| `datasets:*` | Hugging Face, Zenodo, data.gv.at, Kaggle search APIs | ✅ pass | — (`food datasets --search q`, MCP `search_datasets`) |
| `osm-stores` | OpenStreetMap Overpass (supermarket/convenience/organic/chemist) | ✅ pass | ODbL © OSM contributors; `food stores --chain billa --near linz`, MCP `list_stores` |
| hofer.at, spar.at, adeg (direct) | shop sites | 📇 not connected – no public product API (adeg=no webshop; ADEG Flugblatt = per-market Issuu flipbook behind a market selector, no structured data — checked 2026-10-13T20b); branches via `osm-stores` | catalog only |
| FatSecret, Yazio, MyFitnessPal, fddb | calorie apps | 📇 not integrated – FatSecret needs OAuth key (Platform API, free tier); Yazio/MFP/fddb only unofficial private APIs (ToS) | [coddingtonbear/python-myfitnesspal](https://github.com/coddingtonbear/python-myfitnesspal), [juriadams/yazio](https://github.com/juriadams/yazio) listed only |
| BLS 4.0, Swiss FCDB | national composition tables | 📇 catalog (`food datasets`) – file downloads | — |

CLI: `food search|fetch|export|sources|stores|nutri|nutriscore|company|datasets`. MCP (`food-mcp`): `list_sources, search_products, fetch_ready_meals, lookup_ean, list_stores, nutri_lookup, compute_nutriscore, list_nutri_sources, company_lookup, company_children, uid_check, company_impressum, northdata_company, list_datasets, search_datasets`.

## Sources

| id | status | notes |
|---|---|---|
| `billa` | ✅ live | REWE product-discovery API, with nutrition, producer and ID code via `--enrich`. Also covers BILLA Zustellung (delivery to Linz). Category listing `categories/{id}/products` 404 since 2026-10-13; `fetch` falls back to meal search stems. |
| `penny` | ✅ live | Same REWE API. Only the online assortment of about 450 items, no ready meals right now. |
| `gurkerl` | ✅ live | Gurkerl.at (delivers to Linz). Search, prices, **nutrition, ingredients and producer** via `/api/v1/products/{id}/composition`. |
| `lidl` | ❌ blocked | lidl.at `q/api/search` returns 401 to Python clients; Lidl prices come via `heisse-preise`. |
| `spar` | ✅ via heisse-preise | Prices live via dump; images via public CDN `cdn1.interspar.at/.../articleImage.dam/at/{id}/dt_main.jpg` (HEAD-verified 2026-10-13). Product HTML/nutrition still Cloudflare. |
| `spar-shop` | ✅ live | SPAR's own public search API: live price/regular price/€-per-kg/stock by article number (2026-10-13: 122 of 150 'Preis 2025' Spar ready meals confirmed listed with current price; 17 article numbers no longer listed). Weight/counter products (`item_type=WeightProduct`) are priced per 100 g → `extra.price_basis`. |
| `denns` | ✅ live | denn's BioMarkt AT weekly offers (~80/week, land=at). 2026-10-13: 4 ready meals/desserts on offer (MyDeli Bio-Fleischsuppe, SOTO Fingerfood, followfood Airfryer Fish Nuggets, Harvest Moon Protein-Pudding). Full assortment not public; multi-variant offers have a pack range → `size_g=None`. |
| `nah-frisch` | ✅ live (OCR) | Nah&Frisch 'Angebote der Woche' (2 KW tabs, ~36 tiles). 2026-10-13: ready-meal offers iglo Pikante Knödel (3,99 €, 1+1 gratis), Inzersdorfer Fertiggerichte/Suppen 400 g (-25 %, no absolute price), Knorr Kaiserteller Suppen (1,39 €). Image-only tiles → OCR via optional `tesseract` (deu) + Pillow; without tesseract the adapter returns tiles + validity only. |
| `hofer`, `dm-heisse`, `mpreis`, `unimarkt` | ⏳ stale | Taken from the heisse-preise.io dump. Check `extra.price_date`. |
| `unimarkt-shop` | ⛔ closed | shop.unimarkt.at shows only "UNIONLINE hat seinen Service eingestellt" (verified 2026-10-13; closed 02/2024, chain left retail 2026). No live source possible; `unimarkt` dump = history only. |
| `off` | ✅ live | Open Food Facts, AT products, with EAN, nutrition and EMB codes. No prices. |
| `heisse-preise` | ✅ live | Full daily dump, about 200 MB, cached for 12 h. |
| `foodora-market`, `mjam`, `lieferando-shops`, `bio-kistl`, `fittogo`, `adeg`, `wokostswas` | 📇 catalog-only | Researched, but no usable public API (adeg: no online shop; Flugblatt only as per-market Issuu flipbook). `denns` and `nah-frisch` are live offer connectors now (see above). Branches: `osm-stores`. See `food sources`. |

## CLI
```bash
pip install git+https://github.com/servas-ai/food-connectors
food sources
food search "chili con carne" --store gurkerl,billa,lidl --enrich
food fetch --category ready-meals --store gurkerl,billa --enrich -o meals.json   # also appended to ~/.local/share/food-connectors/products.jsonl
food export --since 2026-10-01 --format csv
```

## MCP (stdio)
```json
{"mcpServers": {"food": {"command": "food-mcp"}}}
```
Available tools: `list_sources`, `search_products`, `fetch_ready_meals`, `lookup_ean`.

## Tests
`pytest` runs the offline tests. `LIVE=1 pytest` also runs the network tests.

Please be polite and keep request rates low. These are public frontend endpoints, and each shop's terms apply. MIT licensed.


## Online meal-prep shops

| id | Shop | Notes |
|---|---|---|
| `prepmymeal` | prepmymeal.at | Shopify `/products.json` + Nährwerttabelle der Produktseite |
| `livefresh` | livefresh.at | Shopify, nur Bowls; Nährwerte pro Portion → auf 100 g umgerechnet |
| `gourmetfein` | shop.gourmetfein.com | Shopify, Fleischboxen |

`food fetch --store prepmymeal --enrich` (fit2go.meals: Hydrogen-Shop ohne öffentliche API, noch nicht angebunden)

## Nutrition & quality databases (`food nutri`)

| id | Source | Licence | Status |
|---|---|---|---|
| off-nutri | Open Food Facts API v2 (Nutri-Score, NOVA, Eco-Score, additives, ingredients analysis); nightly dumps: static.openfoodfacts.org/data/openfoodfacts-products.jsonl.gz, Parquet on Hugging Face | ODbL | live |
| usda-fdc | USDA FoodData Central (`FDC_API_KEY`, default `DEMO_KEY`) | CC0 | live |
| ciqual | ANSES CIQUAL 2020 (CSV/XLSX via data.gouv.fr) | Etalab | download |
| swiss-fcdb | Swiss Food Composition Database (naehrwertdaten.ch) | free | catalog |
| bls | Bundeslebensmittelschlüssel 4.0 (blsdb.de) | free download, no redistribution | catalog |
| efsa-openfoodtox | EFSA OpenFoodTox (Zenodo) | CC-BY 4.0 | catalog |
| off-at / opf / oenwt / codecheck | OFF Austria subset / Open Products Facts (non-food) / Österr. Nährwerttabelle / codecheck | – | catalog-only (no API or ToS) |

```
food nutri 4099200053707            # Nutri-Score, NOVA, additives from OFF
food nutri "beef goulash" --sources usda-fdc
food nutriscore --ean 4099200053707 --compute
food nutriscore --compute --kcal 120 --sugar 2 --satfat 1.5 --salt 0.9 --protein 7 --fiber 2
```

`food_connectors/nutri/nutriscore.py` implements the **Nutri-Score 2023** algorithm (general foods) locally. Results carry `"status": "berechnet"` and list assumptions (fruit/veg/legume % defaults to 0 if unknown). On 115 products with an official grade, the local computation matched 106 (92 %).
MCP tools: `nutri_lookup`, `compute_nutriscore`, `list_nutri_sources`. Reuses the public OFF API; the official `openfoodfacts` Python SDK works too but is not required (zero dependencies).

## Firmendaten (`food company`)
```bash
food company "GMS GOURMET GmbH"          # GLEIF: LEI, FN, Adresse, Konzernmutter (strikter Namensabgleich: Rechtsform-/Umlaut-agnostisch, Land der Rechtsadresse muss passen, Score ≥ 0.85)
food company --children 5299003EXF4GJXGELC41
food company --vies ATU12345678          # EU VIES UID-Prüfung
food company "Greisinger GmbH" --northdata   # öffentliche North-Data-Seite (rate-limited) oder API mit NORTHDATA_API_KEY
food company --fn 104525p                # Firmenbuch HVD (FIRMENBUCH_API_KEY, kostenlose Registrierung bei justiz.gv.at)
```
MCP-Tools: `company_lookup`, `company_children`, `uid_check`, `northdata_company`. Rate-limit 1 req/s, Backoff bei 429, keine Bot-Schutz-Umgehung.
Credits: [p-meier/northdata-connectors](https://github.com/p-meier/northdata-connectors), [Lukhers-dev/firmenbuch-HVD](https://github.com/Lukhers-dev/firmenbuch-HVD). Datensatz: [servas-ai/fertiggerichte-daten](https://github.com/servas-ai/fertiggerichte-daten).
