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

## Sources

| id | status | notes |
|---|---|---|
| `billa` | ✅ live | REWE product-discovery API, with nutrition, producer and ID code via `--enrich`. Also covers BILLA Zustellung (delivery to Linz). Server-side search is weak, so `fetch` walks the ready-meal categories. |
| `penny` | ✅ live | Same REWE API. Only the online assortment of about 450 items, no ready meals right now. |
| `gurkerl` | ✅ live | Gurkerl.at (delivers to Linz). Search, prices, **nutrition, ingredients and producer** via `/api/v1/products/{id}/composition`. |
| `lidl` | ⚠️ live, flaky | lidl.at `q/api/search`. Sometimes returns 401 (the client retries). Prices and images only. |
| `spar` | ✅ via heisse-preise | interspar.at product pages and nutrition sit behind Cloudflare, so they need a real browser. |
| `hofer`, `dm`, `mpreis`, `unimarkt` | ⏳ stale | Taken from the heisse-preise.io dump. Check `extra.price_date`. |
| `off` | ✅ live | Open Food Facts, AT products, with EAN, nutrition and EMB codes. No prices. |
| `heisse-preise` | ✅ live | Full daily dump, about 200 MB, cached for 12 h. |
| `foodora-market`, `mjam`, `lieferando-shops`, `bio-kistl`, `fittogo`, `adeg`, `wokostswas` | 📇 catalog-only | Researched, but no usable public API. See `food sources`. |

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
