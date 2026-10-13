"""Minimal dependency-free MCP server over stdio (JSON-RPC 2.0, newline-delimited)."""
import json, sys
from .adapters import ADAPTERS
from .cli import run_many, _stores
TOOLS = [
 {"name": "list_sources", "description": "List all connectors with status and notes.", "inputSchema": {"type": "object", "properties": {}}},
 {"name": "search_products", "description": "Search Austrian grocery products across stores (billa, penny, gurkerl, lidl, spar, hofer, dm, mpreis, unimarkt, off).",
  "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "stores": {"type": "string", "description": "comma list or 'all'"}, "limit": {"type": "integer"}, "enrich": {"type": "boolean", "description": "fetch nutrition/producer details"}}, "required": ["query"]}},
 {"name": "fetch_ready_meals", "description": "Fetch ready meals (Fertiggerichte) from the given stores.",
  "inputSchema": {"type": "object", "properties": {"stores": {"type": "string"}, "limit": {"type": "integer"}, "enrich": {"type": "boolean"}}}},
 {"name": "lookup_ean", "description": "Look up a product by EAN in Open Food Facts.", "inputSchema": {"type": "object", "properties": {"ean": {"type": "string"}}, "required": ["ean"]}},
 {"name": "nutri_lookup", "description": "Nutri-Score, NOVA, Eco-Score, additives, ingredients analysis for an EAN or name (Open Food Facts; also usda-fdc).", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "sources": {"type": "string"}}, "required": ["query"]}},
 {"name": "compute_nutriscore", "description": "Compute Nutri-Score 2023 locally from per-100g values (marked 'berechnet').", "inputSchema": {"type": "object", "properties": {k: {"type": "number"} for k in ("kcal", "sugar", "satfat", "salt", "fiber", "protein", "fvl_pct")}}},
 {"name": "list_nutri_sources", "description": "List nutrition/quality databases with licence and status.", "inputSchema": {"type": "object", "properties": {}}},
]
def call(name, a):
    if name in ("nutri_lookup", "compute_nutriscore", "list_nutri_sources"):
        from .nutri import nutri_lookup, compute_nutriscore, NUTRI_SOURCES
        if name == "nutri_lookup": return nutri_lookup(a["query"], a.get("sources", "off-nutri").split(","))
        if name == "compute_nutriscore": return compute_nutriscore(**a)
        return [{"id": x.id, "name": x.name, "url": x.url, "license": x.license, "status": x.status, "notes": getattr(x, "notes", "")} for x in NUTRI_SOURCES.values()]
    if name == "list_sources": return [x.info() for x in ADAPTERS.values()]
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
