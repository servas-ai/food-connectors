"""Minimal dependency-free MCP server over stdio (JSON-RPC 2.0, newline-delimited)."""
import json, re, sys
from .adapters import ADAPTERS, STORE_ADAPTERS
from .cli import run_many, _stores
TOOLS = [
 {"name": "list_sources", "description": "List all connectors with status and notes.", "inputSchema": {"type": "object", "properties": {}}},
 {"name": "search_products", "description": "Search Austrian grocery products across stores (billa, penny, gurkerl, lidl, spar, hofer, dm (live dm.at product JSON), dm-heisse, mpreis, mpreis-shop (live), spar-shop (live SPAR search API), denns (live denn's BioMarkt AT offers), nah-frisch (live Nah&Frisch weekly offer tiles, OCR), penny-shop (live penny.at online assortment JSON), juit (live), bofrost (live bofrost.at product pages), fittogo (live fittogo.at product HTML), every (live every-foods.com Shopify JSON + product pages), loewenanteil (live loewenanteil.com Shopify JSON + product HTML), kernbeisser (live kernbeisser.at WooCommerce Store API), goldblatt (live goldblatt.at Shopify JSON + product HTML), issmich (live issmich.at Shopware product pages + strict OCR of the Nährwerttabelle image), alfies (live Alfies Wien/Graz online supermarket: public search index + catalogue API), unimarkt, off).",
  "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "stores": {"type": "string", "description": "comma list or 'all'"}, "limit": {"type": "integer"}, "enrich": {"type": "boolean", "description": "fetch nutrition/producer details"}}, "required": ["query"]}},
 {"name": "fetch_ready_meals", "description": "Fetch ready meals (Fertiggerichte) from the given stores.",
  "inputSchema": {"type": "object", "properties": {"stores": {"type": "string"}, "limit": {"type": "integer"}, "enrich": {"type": "boolean"}}}},
 {"name": "lookup_ean", "description": "Look up a product by EAN in Open Food Facts.", "inputSchema": {"type": "object", "properties": {"ean": {"type": "string"}}, "required": ["ean"]}},
 {"name": "nutri_lookup", "description": "Nutri-Score, NOVA, Eco-Score, additives, ingredients analysis for an EAN or name (Open Food Facts; also usda-fdc).", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "sources": {"type": "string"}}, "required": ["query"]}},
 {"name": "compute_nutriscore", "description": "Compute Nutri-Score 2023 locally from per-100g values (marked 'berechnet').", "inputSchema": {"type": "object", "properties": {k: {"type": "number"} for k in ("kcal", "sugar", "satfat", "salt", "fiber", "protein", "fvl_pct")}}},
 {"name": "list_nutri_sources", "description": "List nutrition/quality databases with licence and status.", "inputSchema": {"type": "object", "properties": {}}},
]
TOOLS += [
 {"name": "company_lookup", "description": "Legal entity for a company name via GLEIF: LEI, Firmenbuchnummer/register id, address, direct+ultimate parent.", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "country": {"type": "string"}}, "required": ["name"]}},
 {"name": "company_children", "description": "Direct subsidiaries of a LEI (GLEIF level 2).", "inputSchema": {"type": "object", "properties": {"lei": {"type": "string"}}, "required": ["lei"]}},
 {"name": "uid_check", "description": "Validate EU VAT/UID number via EU VIES.", "inputSchema": {"type": "object", "properties": {"vat": {"type": "string"}}, "required": ["vat"]}},
 {"name": "company_impressum", "description": "Firmenbuchnummer/HRB/UID from a company's public legal notice (Impressum, robots.txt respected), every UID verified via EU VIES; pass domain and expected company name.", "inputSchema": {"type": "object", "properties": {"domain": {"type": "string"}, "name": {"type": "string"}}, "required": ["domain"]}},
 {"name": "northdata_company", "description": "North Data public page facts (or official API with NORTHDATA_API_KEY).", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
]

TOOLS += [{"name": "list_stores", "description": "List grocery store branches near a region via OpenStreetMap Overpass (ODbL). Default near=linz.", "inputSchema": {"type": "object", "properties": {"chain": {"type": "string", "description": "e.g. billa, spar, hofer, denns, mpreis, unimarkt, adeg, nah-frisch"}, "near": {"type": "string", "description": "region key, default linz"}, "limit": {"type": "integer"}}}}]
TOOLS += [{"name": "list_datasets", "description": "Curated open food/price/nutrition datasets with licence, size, freshness.", "inputSchema": {"type": "object", "properties": {}}},
 {"name": "search_datasets", "description": "Live search open datasets on Hugging Face, Zenodo, data.gv.at, Kaggle.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "hubs": {"type": "string"}}, "required": ["query"]}}]

TOOLS += [{"name": "mpreis_product", "description": "Live MPreis webshop product page (schema.org JSON-LD): price, GTIN, brand, image, category, pack size, nutrition per 100 g, ingredients. Pass a /shop/p/ URL.", "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}]

TOOLS += [{"name": "spar_product", "description": "Live SPAR/INTERSPAR article by article number (interspar.at/p/<id>) via SPAR's public search API: current + regular price, €/kg, brand, category, stock status, image (code-internal is SPAR-internal, not a GTIN). Returns null if the article is no longer listed.", "inputSchema": {"type": "object", "properties": {"article_id": {"type": "string"}}, "required": ["article_id"]}}]

TOOLS += [{"name": "denns_offers", "description": "Live denn's BioMarkt Austria weekly offers (public offer feed): name, brand, denn's article no., pack, offer price, regular price, €/kg, validity, vegan/vegetarian flags, image. Optional query filter; ready_meals_only filters soups/ready dishes/desserts.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "ready_meals_only": {"type": "boolean"}}}}]

TOOLS += [{"name": "nahfrisch_offers", "description": "Live Nah&Frisch Austria 'Angebote der Woche' (public weekly offer page): offer tiles per calendar week with validity and official tile image; names/prices via local tesseract OCR when installed (extra.ocr=True, verify visually). Optional query filter; ocr=false returns tiles only.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "ocr": {"type": "boolean"}, "ready_meals_only": {"type": "boolean"}}}}]

TOOLS += [{"name": "penny_product", "description": "Live PENNY Austria article by sku (78-<REWE no.>) or bare REWE article number via penny.at's public product JSON: regular + standard price, promotion text/validity, €/unit, pack, category path, origin, official image. No GTIN/nutrition (use the identical BILLA article 00-<no.>). Returns null if not listed.", "inputSchema": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]}}]

TOOLS += [{"name": "penny_search", "description": "Search the live PENNY Austria online assortment (~450 items, public penny.at product JSON; filtered locally because Penny ignores the search term). ready_meals_only keeps Fertiggerichte/Schnelle Küche/TK-Gerichte/Pizza.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "ready_meals_only": {"type": "boolean"}, "limit": {"type": "integer"}}}}]

TOOLS += [{"name": "juit_dishes", "description": "Live Juit (juit.com, frozen ready meals shipped to Austria) dishes from the public storefront content bundle: name, EAN, net weight, portions, nutrition per 100 g, ingredients, tags, official packshot, sellable flag. Prices are not public (login) and stay null. Optional query filter; include_unsellable adds currently unavailable dishes.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "include_unsellable": {"type": "boolean"}, "limit": {"type": "integer"}}}}]

TOOLS += [{"name": "bofrost_product", "description": "Live bofrost* Austria (frozen home delivery across Austria) product by article number (e.g. 00196) or bofrost.at product URL from the public product page: name, price, €/kg, pack (e.g. 2 x 300 g), availability, nutrition per 100 g, ingredients, portion size, category, official image. No GTIN is published. Returns null if not listed.", "inputSchema": {"type": "object", "properties": {"article": {"type": "string"}}, "required": ["article"]}},
 {"name": "bofrost_search", "description": "Search the live bofrost.at assortment (public product sitemap, ~420 products) by words in the product slug and return parsed product pages (price, €/kg, nutrition, image). ready_meals_only keeps ready-meal categories (Pfannengerichte, Pasta, Schlemmer-Menüs, Hausmannskost, Suppen, Länderküche, Pizza, Fleisch-/Geflügelzubereitungen, vegetarisch/vegan). Polite 1 req/s, keep limit small.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "ready_meals_only": {"type": "boolean"}, "limit": {"type": "integer"}}, "required": ["query"]}}]

TOOLS += [{"name": "fittogo_product", "description": "Live fit2go.meals (fittogo.at, frozen ready meals shipped AT-wide) product by handle or /products/<handle> URL from the public product HTML: name, pack size, pack + per-100g nutrition (kcal/protein/carbs/fat), ingredients, allergens, official packshot. price_eur is the published 12er-box meal price (9,99 €); the individual SKU shows 0,00 €. Returns null if not a ready meal.", "inputSchema": {"type": "object", "properties": {"handle": {"type": "string"}}, "required": ["handle"]}},
 {"name": "fittogo_search", "description": "Search live fit2go.meals assortment (public product sitemap + product HTML) by words in the product slug. Polite 1 req/s; keep limit small.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}]

TOOLS += [{"name": "every_product", "description": "Live every. (every-foods.com, frozen plant-based ready meals shipped to Austria via DPD) meal by Shopify handle or /products/<handle> URL: name, single-meal price (EUR, DE/AT shop), €/kg, weight, nutrition per 100 g and per pack, ingredients, preparation, SKU, availability, official packshot (cdn.shopify.com). No GTIN published. Returns null if unknown.", "inputSchema": {"type": "object", "properties": {"handle": {"type": "string"}}, "required": ["handle"]}},
 {"name": "every_search", "description": "Search the live every. ready-meal assortment (public Shopify products.json, product_type Meal, listed in the DE product sitemap) by words in title/handle/tags (e.g. 'curry', 'gnocchi', 'High in protein') and return parsed meals with nutrition. Polite 1 req/s; keep limit small.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}]

TOOLS += [{"name": "loewenanteil_product", "description": "Live Löwenanteil (loewenanteil.com, Bio glass-jar ready meals; AT selectable on storefront) meal by Shopify handle or /products/<handle> URL: name, single-jar price (EUR), edible size from Nährwerte table, nutrition per 100 g and per glass, ingredients, preparation, SKU, availability, official packshot. No GTIN published. Returns null if unknown.", "inputSchema": {"type": "object", "properties": {"handle": {"type": "string"}}, "required": ["handle"]}},
 {"name": "loewenanteil_search", "description": "Search the live Löwenanteil ready-meal assortment (public Shopify products.json, product_type Fertiggericht, tag single, jar grams ≥800) by words in title/handle/tags and return parsed meals with nutrition. Polite 1 req/s; keep limit small.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}]
TOOLS += [{"name": "kernbeisser_product", "description": "Live Kernbeißer (kernbeisser.at, vegan whole-grain ready meals in 450 g glass jars from Vienna; AT-only delivery, free shipping, min. 6 glasses) meal by product slug, SKU or /produkt/<slug>/ URL: name, price per glass (EUR incl. MwSt.), size, nutrition per 100 g, kcal per jar, ingredients, preparation, GTIN from product JSON-LD, stock, official packshot. Returns null if unknown.", "inputSchema": {"type": "object", "properties": {"slug": {"type": "string"}}, "required": ["slug"]}},
 {"name": "kernbeisser_search", "description": "Search the live Kernbeißer ready-meal assortment (public WooCommerce Store API) by words in name/description (e.g. 'quinoa', 'glutenfrei'); returns parsed meals with nutrition (no GTIN in search results).", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}]
TOOLS += [{"name": "issmich_product", "description": "Live iss mich! (issmich.at, Wiener Bio-Eintöpfe/Suppen im WECK-Pfandglas; Versand nur AT 9,90 €, frei ab 99 €, +2,00 € Pfand/Glas) product by URL or path (e.g. Bio-Shop/Eintoepfe/Fleisch/16/Tex-Mex-Bio-Chili-con-Carne): name, price (EUR incl. MwSt.) + Streichpreis, Pfand, Inhalt (g), GTIN-13, SKU, availability, packshot, Zutaten, Allergene, course (Eintopf/Suppe/Beilage/Süßspeise/Sauce) and nutrition per 100 g + per portion from the official Nährwerttabelle image via strict local OCR (only when consistent with the printed per-portion column + Atwater; else empty with nutrition_image URL). Returns null if not a product page.", "inputSchema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
 {"name": "issmich_search", "description": "Search the live iss mich! Bio-Shop (sitemap + category listings) by words in the product URL slug (umlauts → ae/oe/ue, e.g. 'gulasch', 'suppe vegan', 'linsen'); returns parsed products incl. strict-OCR nutrition when tesseract is installed. Polite 1 req/s; keep limit small.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}]
TOOLS += [{"name": "goldblatt_product", "description": "Live Goldblatt (goldblatt.at, High Protein Bio glass-jar ready meals from Steiermark; ships AT via Post 5,99 € ab 30 € / gratis ab 90 €) meal by Shopify handle or /products/<handle> URL: name, single-jar price (EUR), edible size from Nährwerte table (typically 500 g), nutrition per 100 g and per glass, ingredients, preparation, SKU, availability, official packshot. No GTIN published. Returns null if unknown.", "inputSchema": {"type": "object", "properties": {"handle": {"type": "string"}}, "required": ["handle"]}},
 {"name": "goldblatt_search", "description": "Search the live Goldblatt ready-meal assortment (public Shopify products.json, product_type High Protein Bio-Fertiggerichte, single jars) by words in title/handle/tags and return parsed meals with nutrition. Polite 1 req/s; keep limit small.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}}]


TOOLS += [{"name": "alfies_product", "description": "Live Alfies (alfies.at, Viennese online supermarket: 60-min delivery in Wien, pre-order in Graz; no Linz delivery) product by numeric id, slug or /produkt/<slug> URL: name, brand, price incl. MwSt. and €/kg for the warehouse (altha = Wien default, graz), pack (displayUnit), nutrition per 100 g parsed from the shop's nutrition table (+ plausibility flag), ingredients, preparation, stock, cross-retailer ids (billaId/gurkerlId), official packshot. No GTIN published. Returns null if unknown.", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "warehouse": {"type": "string", "description": "altha (Wien, default) or graz"}}, "required": ["id"]}},
 {"name": "alfies_search", "description": "Search the live Alfies assortment (public search-only index the shop front-end uses) and return only ready meals (Fix & Fertig / Tiefgekühlte Fertiggerichte paths, minus doughs/salads/desserts) with nutrition from the public catalogue API. Polite 1 req/s; keep limit small.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}, "warehouse": {"type": "string"}}, "required": ["query"]}}]

TOOLS += [{"name": "open_prices_lookup", "description": "Crowd-sourced, proof-backed shelf price observations for an EAN from Open Prices (prices.openfoodfacts.org, ODbL): price, currency, date, discount flag, OSM shop (name, brand, city, country), proof type (RECEIPT/PRICE_TAG/...). Newest first; filter by shop country (e.g. AT) and since date. User contributions, not retailer feeds — check date and shop before using as a current price.", "inputSchema": {"type": "object", "properties": {"ean": {"type": "string"}, "country": {"type": "string"}, "since": {"type": "string", "description": "YYYY-MM-DD"}}, "required": ["ean"]}}]


def call(name, a):
    if name == "open_prices_lookup":
        from .open_prices import prices as _op
        return _op(a["ean"], a.get("country"), a.get("since"))
    if name == "alfies_product":
        from .adapters.alfies import product as _al
        r = _al(a["id"], a.get("warehouse") or "altha"); return r.to_dict() if r else None
    if name == "alfies_search":
        from .adapters.alfies import Alfies
        return [p.to_dict() for p in Alfies().search(a["query"], limit=min(a.get("limit") or 10, 20), warehouse=a.get("warehouse") or "altha")]
    if name == "every_product":
        from .adapters.every import product
        p = product(a["handle"]); return p.to_dict() if p else None
    if name == "every_search":
        from .adapters.every import Every
        return [p.to_dict() for p in Every().search(a["query"], limit=min(a.get("limit") or 10, 20))]
    if name == "kernbeisser_product":
        from .adapters.kernbeisser import product as _kb
        r = _kb(a["slug"]); return r.to_dict() if r else None
    if name == "kernbeisser_search":
        from .adapters.kernbeisser import Kernbeisser
        return [p.to_dict() for p in Kernbeisser().search(a["query"], limit=min(a.get("limit") or 10, 20))]
    if name == "loewenanteil_product":
        from .adapters.loewenanteil import product
        p = product(a["handle"]); return p.to_dict() if p else None
    if name == "loewenanteil_search":
        from .adapters.loewenanteil import Loewenanteil
        return [p.to_dict() for p in Loewenanteil().search(a["query"], limit=min(a.get("limit") or 10, 20))]
    if name == "issmich_product":
        from .adapters.issmich import product as _im
        r = _im(a["url"]); return r.to_dict() if r else None
    if name == "issmich_search":
        from .adapters.issmich import IssMich
        return [p.to_dict() for p in IssMich().search(a["query"], limit=min(a.get("limit") or 10, 20))]
    if name == "goldblatt_product":
        from .adapters.goldblatt import product as _gb
        r = _gb(a["handle"]); return r.to_dict() if r else None
    if name == "goldblatt_search":
        from .adapters.goldblatt import Goldblatt
        return [p.to_dict() for p in Goldblatt().search(a["query"], limit=min(a.get("limit") or 10, 20))]


    if name == "fittogo_product":
        from .adapters.fittogo import parse_product, is_ready_meal, BASE
        from .http import get
        handle = a["handle"].strip().rstrip("/").split("/")[-1]
        url = handle if handle.startswith("http") else f"{BASE}/products/{handle}"
        try:
            h = get(url, raw=True, timeout=40).decode("utf-8", "replace")
        except Exception:
            return None
        p = parse_product(h, url)
        return p.to_dict() if is_ready_meal(p) else None
    if name == "fittogo_search":
        from .adapters.fittogo import FitToGo
        return [p.to_dict() for p in FitToGo().search(a["query"], limit=min(a.get("limit") or 10, 20))]
    if name == "bofrost_product":
        from .adapters.bofrost import product
        p = product(a["article"]); return p.to_dict() if p else None
    if name == "bofrost_search":
        import time
        from .adapters.bofrost import product_urls, product, is_meal_url, is_ready_meal
        fold = lambda s: s.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        q = re.findall(r"\w{3,}", a.get("query") or ""); urls = product_urls()
        hits = [u for u in urls if all(fold(w) in fold(u) for w in q) and (not a.get("ready_meals_only") or is_meal_url(u))][: min(a.get("limit") or 10, 30)]
        out = []
        for u in hits:
            p = product(u, urls); time.sleep(1.0)
            if p and (not a.get("ready_meals_only") or is_ready_meal(p)): out.append(p.to_dict())
        return out
    if name == "juit_dishes":
        from .adapters.juit import dishes, to_product
        q = re.findall(r"\w{3,}", (a.get("query") or "").lower())
        ps = [to_product(f) for f in dishes()]
        ps = [p for p in ps if (a.get("include_unsellable") or p.extra["sellable"]) and all(w in f"{p.name} {p.category}".lower() for w in q)]
        return [p.to_dict() for p in ps[: a.get("limit") or 100]]
    if name == "penny_product":
        from .adapters.penny_shop import product
        p = product(a["sku"]); return p.to_dict() if p else None
    if name == "penny_search":
        from .adapters.penny_shop import listing, to_product, is_ready_meal
        q = re.findall(r"\w{3,}", (a.get("query") or "").lower())
        ps = [to_product(r) for r in listing()]
        ps = [p for p in ps if all(w in f"{p.name} {p.brand or ''} {p.category or ''}".lower() for w in q) and (not a.get("ready_meals_only") or is_ready_meal(p))]
        return [p.to_dict() for p in ps[: a.get("limit") or 50]]
    if name == "nahfrisch_offers":
        from .adapters.nah_frisch import offers, to_product, is_ready_meal
        ps = [to_product(o, a.get("ocr")) for o in offers()]
        q = (a.get("query") or "").lower()
        return [p.to_dict() for p in ps if (not q or q in (p.name or "").lower()) and (not a.get("ready_meals_only") or is_ready_meal(p))]
    if name == "denns_offers":
        from .adapters.denns import offers, to_product, is_ready_meal
        ps = [to_product(n) for n in offers()]
        q = (a.get("query") or "").lower()
        return [p.to_dict() for p in ps if (not q or q in p.name.lower()) and (not a.get("ready_meals_only") or is_ready_meal(p))]
    if name == "spar_product":
        from .adapters.spar_shop import article
        p = article(a["article_id"]); return p.to_dict() if p else None
    if name == "mpreis_product":
        from .adapters.mpreis_shop import product
        p = product(a["url"]); return p.to_dict() if p else None
    if name == "list_stores":
        from .adapters.osm_stores import fetch_stores
        rows = fetch_stores(near=a.get("near", "linz"), chain=a.get("chain"), limit=a.get("limit", 500))
        return {"count": len(rows), "licence": "ODbL 1.0 © OpenStreetMap contributors", "stores": rows}
    if name in ("list_datasets", "search_datasets"):
        from . import datasets as D
        return D.CATALOG if name == "list_datasets" else D.search(a["query"], (a.get("hubs") or "hf,zenodo,datagv,kaggle").split(","))
    if name in ("company_lookup", "company_children", "uid_check", "northdata_company", "company_impressum"):
        from . import company as C
        return {"company_lookup": lambda: C.company(a["name"], a.get("country")), "company_children": lambda: C.gleif_children(a["lei"]),
                "uid_check": lambda: C.vies_check(a["vat"]), "northdata_company": lambda: C.northdata_page(a["name"]), "company_impressum": lambda: C.impressum(a["domain"], a.get("name"))}[name]()
    if name in ("nutri_lookup", "compute_nutriscore", "list_nutri_sources"):
        from .nutri import nutri_lookup, compute_nutriscore, NUTRI_SOURCES
        if name == "nutri_lookup": return nutri_lookup(a["query"], a.get("sources", "off-nutri").split(","))
        if name == "compute_nutriscore": return compute_nutriscore(**a)
        return [{"id": x.id, "name": x.name, "url": x.url, "license": x.license, "status": x.status, "notes": getattr(x, "notes", "")} for x in NUTRI_SOURCES.values()]
    if name == "list_sources": return [x.info() for x in list(ADAPTERS.values()) + list(STORE_ADAPTERS.values())]
    if name == "search_products":
        r, e = run_many(_stores(a.get("stores", "billa,gurkerl,lidl,off")), lambda ad: ad.search(a["query"], a.get("limit", 20)), a.get("enrich", False))
        return {"errors": e, "products": [p.to_dict() for p in r]}
    if name == "fetch_ready_meals":
        r, e = run_many(_stores(a.get("stores", "gurkerl")), lambda ad: ad.fetch("ready-meals", a.get("limit", 100)), a.get("enrich", False))
        return {"errors": e, "products": [p.to_dict() for p in r]}
    if name == "lookup_ean":
        p = ADAPTERS["off"].by_ean(a["ean"]); return p.to_dict() if p else None
    raise ValueError(f"unknown tool {name}")
def handle(m):
    meth, mid = m.get("method"), m.get("id")
    if meth == "initialize":
        res = {"protocolVersion": m.get("params", {}).get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}}, "serverInfo": {"name": "food-connectors", "version": "0.1.0"}}
    elif meth == "tools/list": res = {"tools": TOOLS}
    elif meth == "tools/call":
        p = m["params"]
        try: res = {"content": [{"type": "text", "text": json.dumps(call(p["name"], p.get("arguments") or {}), ensure_ascii=False)}]}
        except Exception as e: res = {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}
    elif meth == "ping": res = {}
    elif mid is None: return None
    else: return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}
def serve():
    for line in sys.stdin:
        if not line.strip(): continue
        r = handle(json.loads(line))
        if r is not None: sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n"); sys.stdout.flush()
if __name__ == "__main__": serve()
