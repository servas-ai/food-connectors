"""OpenStreetMap Overpass live query for Austrian grocery store branches (ODbL)."""
from __future__ import annotations
import json, re, urllib.parse, urllib.request
from datetime import datetime, timezone

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = "food-connectors/0.1 (osm-stores; +https://github.com/servas-ai/food-connectors)"

# Named regions → (south, west, north, east)
REGIONS = {
    "linz": (48.15, 13.95, 48.45, 14.55),  # Linz + Linz-Land + Urfahr-Umgebung (approx)
}

# Chain filter aliases → regex matched against brand|name|operator
CHAIN_PAT = {
    "billa": r"\bbilla\b",
    "billa-plus": r"\bbilla\s*plus\b",
    "spar": r"\bspar\b",
    "eurospar": r"\beurospar\b",
    "interspar": r"\binterspar\b",
    "hofer": r"\bhofer\b|\baldi\b",
    "lidl": r"\blidl\b",
    "penny": r"\bpenny\b",
    "dm": r"\bdm\b",
    "mpreis": r"\bmpreis\b",
    "unimarkt": r"\bunimarkt\b",
    "adeg": r"\badeg\b",
    "nah-frisch": r"nah\s*&?\s*frisch",
    "denns": r"denn'?s|denns\s*bio",
    "bipa": r"\bbipa\b",
}

RULES = [
    (r"\bbilla\s*plus\b", "Billa Plus"),
    (r"\bbilla\b", "Billa"),
    (r"\beurospar\b", "Eurospar"),
    (r"\binterspar\b", "Interspar"),
    (r"\bspar\s*express\b", "Spar Express"),
    (r"\bspar\b", "Spar"),
    (r"\bhofer\b|\baldi\b", "Hofer"),
    (r"\blidl\b", "Lidl"),
    (r"\bpenny\b", "Penny"),
    (r"\bdm\b", "dm"),
    (r"\bbipa\b", "Bipa"),
    (r"\bmpreis\b", "MPreis"),
    (r"\bunimarkt\b", "Unimarkt"),
    (r"\badeg\b", "ADEG"),
    (r"nah\s*&?\s*frisch", "Nah&Frisch"),
    (r"denn'?s|denns\s*bio", "denn's BioMarkt"),
]

def _chain_label(tags: dict) -> str:
    blob = " ".join(filter(None, [tags.get("brand"), tags.get("name"), tags.get("operator")])).lower()
    for pat, label in RULES:
        if re.search(pat, blob, re.I):
            return label
    if tags.get("shop") == "organic" or re.search(r"\bbio\b|naturkost", blob):
        return "Bio (sonstige)"
    return tags.get("brand") or tags.get("name") or tags.get("shop") or "?"

def _query(bbox, chain: str | None = None) -> str:
    s, w, n, e = bbox
    filt = ""
    if chain:
        key = chain.lower().strip()
        pat = CHAIN_PAT.get(key) or re.escape(chain)
        # Overpass can't do arbitrary regex on combined fields easily; filter client-side.
        # Keep shop filter broad.
        _ = pat
    return f"""
[out:json][timeout:90];
(
  node["shop"~"supermarket|convenience|organic|chemist"]({s},{w},{n},{e});
  way["shop"~"supermarket|convenience|organic|chemist"]({s},{w},{n},{e});
);
out center tags;
"""

def fetch_stores(near: str = "linz", chain: str | None = None, limit: int = 500) -> list[dict]:
    """Live Overpass query. Returns store dicts (ODbL attribution required)."""
    bbox = REGIONS.get((near or "linz").lower())
    if not bbox:
        raise ValueError(f"unknown region {near!r}; known: {sorted(REGIONS)}")
    q = _query(bbox, chain)
    req = urllib.request.Request(
        OVERPASS,
        data=urllib.parse.urlencode({"data": q}).encode(),
        headers={"User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = json.loads(r.read().decode())
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    chain_key = (chain or "").lower().strip()
    chain_re = re.compile(CHAIN_PAT[chain_key], re.I) if chain_key in CHAIN_PAT else (
        re.compile(re.escape(chain), re.I) if chain else None
    )
    out = []
    for e in payload.get("elements", []):
        tags = e.get("tags") or {}
        if e.get("type") == "way":
            lat = (e.get("center") or {}).get("lat")
            lon = (e.get("center") or {}).get("lon")
        else:
            lat, lon = e.get("lat"), e.get("lon")
        if lat is None or lon is None:
            continue
        blob = " ".join(filter(None, [tags.get("brand"), tags.get("name"), tags.get("operator")]))
        if chain_re and not chain_re.search(blob):
            continue
        out.append({
            "osm_type": e.get("type"),
            "osm_id": e.get("id"),
            "chain": _chain_label(tags),
            "name": tags.get("name") or tags.get("brand") or "",
            "street": tags.get("addr:street") or "",
            "housenumber": tags.get("addr:housenumber") or "",
            "postcode": tags.get("addr:postcode") or "",
            "city": tags.get("addr:city") or tags.get("addr:place") or "",
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "opening_hours": tags.get("opening_hours") or "",
            "brand_wikidata": tags.get("brand:wikidata") or "",
            "source": "OpenStreetMap contributors, ODbL",
            "fetched_at": fetched_at,
            "near": near,
        })
        if len(out) >= limit:
            break
    return out


class OsmStores:
    """Adapter-shaped helper (not a product Adapter) for CLI/MCP store listing."""
    id = "osm-stores"
    store = "OpenStreetMap"
    homepage = "https://www.openstreetmap.org"
    status = "live"
    notes = (
        "Live Overpass query for supermarket/convenience/organic/chemist in named regions "
        "(default: Linz+Umland). Licence: ODbL 1.0 — © OpenStreetMap contributors. "
        "CLI: food stores --chain X --near linz · MCP: list_stores"
    )
    def info(self):
        return {"id": self.id, "store": self.store, "homepage": self.homepage, "status": self.status, "notes": self.notes}
    def list_stores(self, chain=None, near="linz", limit=500):
        return fetch_stores(near=near, chain=chain, limit=limit)
