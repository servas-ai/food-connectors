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
| `juit` | Juit public storefront content bundle `cdn.juit.gmbh/content-de.json` (the Contentful export juit.com itself loads; juit.com robots only disallows /order /profile /checkout /thankyou; no login/cookies). CLI `food fetch --store juit` / `food search … --store juit`, MCP `juit_dishes` | ✅ live (frozen ready meals shipped to Austria via DHL Express, 8,99 €: 116 dish entries, 50 sellable on 2026-10-14 — EAN, net weight, portions, nutrition per 100 g, ingredients, tags, official packshot cdn.juit.gmbh; **no prices**: api.juitnow.com price lists answer 401 → `price_eur=None`, never estimated) | Juit GmbH, Bielefeld (HRB 42921) |
| `bofrost` | bofrost* Austria public shop pages: sitemap index `bofrost.at/sitemap.xml` → PRODUCT sitemap (~420 URLs) → product pages with schema.org JSON-LD Product (price, availability, images), pack line with €/kg, nutrition table per 100 g, ingredients, Nutri-Score badge (robots `*` disallows only /cart /checkout /account /shop/ajax/ /crm — none used; no login/cookies; 1 req/s). CLI `food fetch --store bofrost` / `food search … --store bofrost`, MCP `bofrost_product`, `bofrost_search` | ✅ live (frozen home delivery across Austria by bofrost* drivers, 14 Niederlassungen incl. Sattledt OÖ: 2026-10-14 154 ready-meal candidates → 144 finished dishes, all with price, €/kg, pack size, nutrition, Nutri-Score and HEAD-200 photo; **no GTIN** on bofrost.at → `ean=None`) | bofrost* Austria GmbH, Ötztal-Bahnhof (FN 185873v) Courses: `fetch(category="desserts")` = warm Mehlspeisen (Knödel, Schmarrn, Nockerl, Mohnnudeln, Strudel, Palatschinken; no Torten/Eis/raw dough), `fetch(category="starters")` = warm Vorspeisen (Frühlingsrollen, Teigtaschen, Flammkuchen, Kaspressknödel; since 2026-10-16T19 also Pizzettis, Rösti-Baguette, Gemüse-/Broccoli-Laibchen, Schinken-Käse-Röllchen — breaded cheese stays out) — added 2026-10-16. Default ready-meals now also match Schlemmerfilet. |
| `every` | every. (every-foods.com) public Shopify storefront JSON `eat.every-foods.com/products.json` (single-meal price EUR, SKU, availability, packshots on cdn.shopify.com) + public product pages `every-foods.com/products/<handle>` (Next.js/Storyblok `product` blok: weight, nutrition table per 100 g + per pack, ingredients, preparation); ready meals = product_type `Meal`, price > 0, listed in `sitemap-products.xml` (robots `*` disallows only /account /api /discount; no login/cookies; 1 req/s). CLI `food fetch --store every` / `food search … --store every`, MCP `every_product`, `every_search` | ✅ live (frozen plant-based ready meals; AT delivery via DPD per the shop's shipping policy, 5,99 €, free from 8 meals: 2026-10-14 54 candidates → 50 meals with price, weight, nutrition, ingredients and HEAD-200 photo; 4 without published nutrition dropped; **no GTIN** → `ean=None`) | Every. GmbH, Berlin (HRB 221768 B) |
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
| `open-prices` | Open Prices (prices.openfoodfacts.org) public REST API, ODbL | ✅ pass (2026-10-16) | — (`food prices EAN --country AT --since YYYY-MM-DD`, MCP `open_prices_lookup`; crowd-sourced, dated, OSM-located observations with proof type) |
| `datasets:*` | Hugging Face, Zenodo, data.gv.at, Kaggle search APIs | ✅ pass | — (`food datasets --search q`, MCP `search_datasets`) |
| `osm-stores` | OpenStreetMap Overpass (supermarket/convenience/organic/chemist) | ✅ pass | ODbL © OSM contributors; `food stores --chain billa --near linz`, MCP `list_stores` |
| spar.at, adeg (direct) | shop sites | 📇 not connected – no public product API (hofer.at → live `hofer-shop` since 2026-10-17) (adeg=no webshop; ADEG Flugblatt = per-market Issuu flipbook behind a market selector, no structured data — checked 2026-10-13T20b); branches via `osm-stores` | catalog only |
| FatSecret, Yazio, MyFitnessPal, fddb | calorie apps | 📇 not integrated – FatSecret needs OAuth key (Platform API, free tier); Yazio/MFP/fddb only unofficial private APIs (ToS) | [coddingtonbear/python-myfitnesspal](https://github.com/coddingtonbear/python-myfitnesspal), [juriadams/yazio](https://github.com/juriadams/yazio) listed only |
| BLS 4.0, Swiss FCDB | national composition tables | 📇 catalog (`food datasets`) – file downloads | — |

CLI: `food search|fetch|export|sources|stores|nutri|nutriscore|company|datasets|prices`. MCP (`food-mcp`): `list_sources, search_products, fetch_ready_meals, lookup_ean, list_stores, nutri_lookup, compute_nutriscore, list_nutri_sources, company_lookup, company_children, uid_check, company_impressum, northdata_company, list_datasets, search_datasets, open_prices_lookup, myproduct_product, myproduct_search, hofer_product, hofer_search` (+ per-store live tools).

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
| `juit` | ✅ live | Juit frozen ready meals (online, ships to AT). 2026-10-14: 50 sellable dishes, all with EAN + nutrition + packshot (images 50/50 HEAD 200); unsellable dishes via `include_unsellable`. Prices only behind login (401) → null. |
| `bofrost` | ✅ live | bofrost* Austria frozen ready meals (home delivery). 2026-10-14: 144 finished dishes (Pfannengerichte, Pasta, Schlemmer-Menüs, Hausmannskost, Suppen, Länderküche, Pizza, Fleisch-/Geflügelzubereitungen, vegetarisch/vegan); desserts/ice/sides/plain Knödel/Suppeneinlagen filtered by `is_ready_meal`. Median 13,79 € per pack. |
| `every` | ✅ live | every. frozen plant-based ready meals (bowls, curries, pasta, stews, salads), shipped to AT (DPD). 2026-10-14: 50 meals, median 8,99 € / 450 g single price (bundles/subscription cheaper); some Storyblok tables are English ('Typical values') → bilingual parser; per-pack column typos flagged in `extra.pack_inconsistent` (per 100 g is used). AGB §6 still says DE-only while the shipping policy lists Österreich — documented. |
| `hofer-shop` | ✅ live | HOFER Österreich (hofer.at, ALDI SÜD Nuxt front, 2026-10-17): public `sitemap_products.xml` (1298 product URLs) + server-rendered product pages (`__NUXT_DATA__` devalue payload + JSON-LD Offer). robots.txt `*` disallows only /tools and the search `/*?q=` (never used); polite 1 req/s; a 403 is raised, never worked around. Per product: name, brand, Regalpreis (random-weight pieces: price per piece + €/kg), €/kg or €/l, selling size, 'Verfügbar seit', ingredients, storage/usage, allergens, discontinued flag, official packshot (Aldi Scene7, width templated). No GTIN/nutrition published → empty, never estimated. `fetch` = slug prefilter (95/1298) → page → strict meal filter (raw meat via 'Rohes Fleisch'/'100% …fleisch', sauces, pasta, legumes, bakery excluded): 18 current heat-up meals on 2026-10-17. CLI `food fetch|search --store hofer-shop`, MCP `hofer_product` / `hofer_search`. |
| `myproduct` | ✅ live | myProduct (myproduct.at) — Austrian online marketplace for regional producers (myProduct GmbH, Zwettl, FN 431059k), category Fertiggerichte: page dataLayer + tile links → product pages (schema.org JSON-LD Offer + Magento attribute table: EAN, Nettofüllmenge, Herstellerangaben with address, Zutaten, Allergene, Lagerhinweis, MHD, bio/vegan, Nährwerte je 100 g when published, Atwater-checked). 2026-10-16: 218 category items → 64 finished dishes/soups (Hartls Kulinarikum Linz 19, Little Lunch 9, Rettergut 5, Danke Bauer 4, Goldblatt 4 …), 63 with valid EAN, 64/64 HEAD-200 packshots, 11 with a published nutrition table (rest say 'gesetzlich keine Nährwertkennzeichnung notwendig' → never estimated); fonds, sauces/Bolognese, spreads, dry mixes, soup powders, meat-substitute raw goods excluded with reason. Shipping 7,90 € per 10 kg within AT. CLI `food fetch|search --store myproduct`, MCP `myproduct_product` / `myproduct_search`. |
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
