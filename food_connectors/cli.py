import argparse, concurrent.futures as cf, datetime as dt, json, os, sys
from .adapters import ADAPTERS, STORE_ADAPTERS
DB = os.path.expanduser(os.environ.get("FOOD_DB", "~/.local/share/food-connectors/products.jsonl"))

def _save(products):
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with open(DB, "a") as f:
        for p in products: f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")

def _stores(arg):
    if not arg or arg == "all": return [a for a in ADAPTERS.values() if a.status != "catalog-only"]
    return [ADAPTERS[s] for s in arg.split(",")]

def run_many(stores, fn, enrich=False, workers=6):
    out, errors = [], {}
    def one(a):
        res = fn(a)
        if enrich:
            with cf.ThreadPoolExecutor(workers) as ex: res = list(ex.map(a.enrich, res))
        return res
    with cf.ThreadPoolExecutor(len(stores) or 1) as ex:
        futs = {ex.submit(one, a): a.id for a in stores}
        for f in cf.as_completed(futs):
            try: out += f.result()
            except Exception as e: errors[futs[f]] = repr(e)[:200]
    return out, errors

def main(argv=None):
    ap = argparse.ArgumentParser(prog="food", description="Austrian grocery / ready-meal connectors")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("search"); s.add_argument("q"); s.add_argument("--store", default="all"); s.add_argument("--limit", type=int, default=20); s.add_argument("--enrich", action="store_true")
    f = sp.add_parser("fetch"); f.add_argument("--category", default="ready-meals"); f.add_argument("--store", default="billa,penny,gurkerl"); f.add_argument("--limit", type=int, default=500); f.add_argument("--enrich", action="store_true"); f.add_argument("-o", "--out")
    e = sp.add_parser("export"); e.add_argument("--since", help="ISO date/time"); e.add_argument("--store"); e.add_argument("--format", choices=["json", "jsonl", "csv"], default="json")
    sp.add_parser("sources"); sp.add_parser("mcp")
    st = sp.add_parser("stores", help="List grocery branches via OpenStreetMap Overpass (ODbL)"); st.add_argument("--chain"); st.add_argument("--near", default="linz"); st.add_argument("--limit", type=int, default=500)
    ds = sp.add_parser("datasets", help="Open dataset catalog; --search q queries HF/Zenodo/data.gv.at/Kaggle live"); ds.add_argument("--search"); ds.add_argument("--hubs", default="hf,zenodo,datagv,kaggle")
    nu = sp.add_parser("nutri", help="Nutri-Score/NOVA/additives by EAN or name"); nu.add_argument("q"); nu.add_argument("--sources", default="off-nutri")
    ns = sp.add_parser("nutriscore", help="Nutri-Score 2023 (official from OFF or --compute locally)"); ns.add_argument("--compute", action="store_true")
    for k in ("kcal", "sugar", "satfat", "salt", "fiber", "protein", "fvl"): ns.add_argument("--" + k, type=float)
    ns.add_argument("--ean")
    co = sp.add_parser("company", help="Company registry lookup (GLEIF/FN/parents, --vies UID, --northdata, --children LEI)")
    co.add_argument("name", nargs="?"); co.add_argument("--country"); co.add_argument("--vies"); co.add_argument("--northdata", action="store_true"); co.add_argument("--children"); co.add_argument("--fn", help="Firmenbuch HVD lookup (needs FIRMENBUCH_API_KEY)")
    a = ap.parse_args(argv)
    if a.cmd == "stores":
        from .adapters.osm_stores import fetch_stores
        rows = fetch_stores(near=a.near, chain=a.chain, limit=a.limit)
        print(json.dumps({"count": len(rows), "licence": "ODbL 1.0 © OpenStreetMap contributors", "stores": rows}, ensure_ascii=False, indent=1)); return
    if a.cmd == "datasets":
        from . import datasets as D
        print(json.dumps(D.search(a.search, a.hubs.split(",")) if a.search else D.CATALOG, ensure_ascii=False, indent=1)); return
    if a.cmd == "company":
        from . import company as C
        out = C.vies_check(a.vies) if a.vies else C.gleif_children(a.children) if a.children else C.firmenbuch_hvd(a.fn) if a.fn else C.northdata_page(a.name) if a.northdata else C.company(a.name, a.country)
        print(json.dumps(out, ensure_ascii=False, indent=1)); return
    if a.cmd == "sources":
        print(json.dumps([x.info() for x in list(ADAPTERS.values()) + list(STORE_ADAPTERS.values())], ensure_ascii=False, indent=1)); return
    if a.cmd == "nutri":
        from .nutri import nutri_lookup; print(json.dumps(nutri_lookup(a.q, a.sources.split(",")), ensure_ascii=False, indent=1)); return
    if a.cmd == "nutriscore":
        from .nutri import compute_nutriscore, nutri_lookup
        v = dict(kcal=a.kcal, sugar=a.sugar, satfat=a.satfat, salt=a.salt, fiber=a.fiber, protein=a.protein, fvl_pct=a.fvl)
        if a.ean:
            r = (nutri_lookup(a.ean) or [None])[0]
            if r and r["nutriscore"] and not a.compute: print(json.dumps(r, ensure_ascii=False)); return
            if r: v = {**{k: r["nutrition_100g"].get(k) for k in ("kcal","sugar","satfat","salt","fiber","protein")}, "fvl_pct": r.get("fvl_pct"), **{k: x for k, x in v.items() if x is not None}}
        print(json.dumps(compute_nutriscore(**v), ensure_ascii=False, indent=1)); return
    if a.cmd == "mcp":
        from .mcp_server import serve; serve(); return
    if a.cmd == "search":
        res, err = run_many(_stores(a.store), lambda ad: ad.search(a.q, a.limit), a.enrich)
    elif a.cmd == "fetch":
        res, err = run_many(_stores(a.store), lambda ad: ad.fetch(a.category, a.limit), a.enrich)
        _save(res)
    else:
        rows = [json.loads(l) for l in open(DB)] if os.path.exists(DB) else []
        if a.since: rows = [r for r in rows if r["fetched_at"] >= a.since]
        if a.store: rows = [r for r in rows if r["source"] in a.store.split(",")]
        if a.format == "jsonl": [print(json.dumps(r, ensure_ascii=False)) for r in rows]
        elif a.format == "csv":
            import csv; w = csv.writer(sys.stdout); cols = ["source", "store", "name", "brand", "price_eur", "unit_price_eur", "size_g", "ean", "producer", "producer_id", "source_url", "fetched_at"]
            w.writerow(cols + ["kcal", "protein", "salt"]); [w.writerow([r.get(c) for c in cols] + [r["nutrition_100g"].get(k) for k in ("kcal", "protein", "salt")]) for r in rows]
        else: print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    data = [p.to_dict() for p in res]
    txt = json.dumps({"count": len(data), "errors": err, "products": data}, ensure_ascii=False, indent=1)
    if getattr(a, "out", None): open(a.out, "w").write(txt); print(f"{len(data)} products -> {a.out}; errors={err}", file=sys.stderr)
    else: print(txt)

if __name__ == "__main__": main()
