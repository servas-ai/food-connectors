"""Adapters for open company registries. Stdlib only. Polite: 1 req/s, UA set, backoff on 429."""
import json, os, re, time, urllib.parse, urllib.request, html

UA = "food-connectors/0.1 (+https://github.com/servas-ai/fertiggerichte-daten)"
_last = [0.0]

def _get(url, data=None, headers=None, tries=3, timeout=25):
    for i in range(tries):
        wait = 1.1 - (time.time() - _last[0])
        if wait > 0: time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(5 * (i + 1)); continue
            if e.code == 404: return None
            raise
    return None

def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# ---------- GLEIF (CC0) ----------
GLEIF = "https://api.gleif.org/api/v1"

def _lei(rec):
    a = rec["attributes"]; e = a["entity"]; la = e["legalAddress"]
    return {
        "lei": rec["id"], "legal_name": e["legalName"]["name"],
        "register_id": e.get("registeredAs"), "register_ra": (e.get("registeredAt") or {}).get("id"),
        "legal_form": (e.get("legalForm") or {}).get("id"), "status": e.get("status"),
        "jurisdiction": e.get("jurisdiction"),
        "address": ", ".join(filter(None, [" ".join(la.get("addressLines") or []), (la.get("postalCode") or "") + " " + (la.get("city") or ""), la.get("country")])),
        "country": la.get("country"), "creation_date": e.get("creationDate"),
        "registration_status": a["registration"].get("status"),
        "source": f"{GLEIF}/lei-records/{rec['id']}", "fetched_at": now(),
    }

def gleif_search(name, country=None, size=5):
    q = f"{GLEIF}/lei-records?filter[fulltext]={urllib.parse.quote(name)}&page[size]={size}"
    if country: q += f"&filter[entity.legalAddress.country]={country}"
    d = json.loads(_get(q) or '{"data":[]}')
    return [_lei(r) for r in d["data"]]

def gleif_parents(lei):
    out = {}
    for kind in ("direct-parent", "ultimate-parent"):
        t = _get(f"{GLEIF}/lei-records/{lei}/{kind}")
        if t:
            try: out[kind.replace("-", "_")] = _lei(json.loads(t)["data"])
            except Exception: pass
    return out

def gleif_children(lei, size=50):
    t = _get(f"{GLEIF}/lei-records/{lei}/direct-children?page[size]={size}")
    return [_lei(r) for r in json.loads(t)["data"]] if t else []

# ---------- EU VIES (UID check) ----------
def vies_check(vat):
    vat = vat.replace(" ", "").upper(); cc, num = vat[:2], vat[2:]
    t = _get("https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number",
             data=json.dumps({"countryCode": cc, "vatNumber": num}).encode(),
             headers={"Content-Type": "application/json"})
    d = json.loads(t); d["source"] = "EU VIES"; d["fetched_at"] = now(); return d

# ---------- North Data (public pages only, respect ToS; no stealth) ----------
def northdata_page(name, city=None):
    """Fetch the public North Data company page and extract register id + snippet facts.
    North Data rate-limits anonymous use (HTTP 429); for bulk use their paid API (NORTHDATA_API_KEY)."""
    key = os.environ.get("NORTHDATA_API_KEY")
    if key:
        q = urllib.parse.urlencode({"name": name, "address": city or "", "api_key": key, "financials": "true", "relations": "true"})
        t = _get("https://www.northdata.com/_api/company/v1/company?" + q)
        return json.loads(t) if t else None
    slug = urllib.parse.quote_plus(name + (", " + city if city else ""))
    url = f"https://www.northdata.de/{slug}"
    try: t = _get(url, tries=2)
    except Exception as e: return {"error": str(e), "source": url}
    if not t: return None
    txt = html.unescape(re.sub(r"<[^>]+>", " ", t))
    m = re.search(r"\bFN\s?(\d{3,6}\s?[a-z])\b", txt)
    desc = re.search(r'<meta name="description" content="([^"]+)"', t)
    return {"fn": m.group(1).replace(" ", "") if m else None,
            "description": html.unescape(desc.group(1)) if desc else None,
            "source": url, "fetched_at": now()}

# ---------- Austrian Firmenbuch HVD (needs free API key from justiz.gv.at) ----------
def firmenbuch_hvd(fn):
    key = os.environ.get("FIRMENBUCH_API_KEY")
    if not key:
        return {"error": "set FIRMENBUCH_API_KEY (free registration: https://www.justiz.gv.at/service/datenbanken/firmenbuch/hvd)"}
    t = _get(f"https://justizonline.gv.at/jop/api/at.gv.justiz.fbw/ws/hvd/v1/firma?fnr={urllib.parse.quote(fn)}",
             headers={"X-API-KEY": key})
    return json.loads(t) if t else None

def _norm(x):
    x = (x or "").lower().replace("ö","oe").replace("ü","ue").replace("ä","ae").replace("ß","ss")
    return set(t for t in re.findall(r"[a-z0-9]+", x) if t not in {"gmbh","ag","kg","co","und","the","bv","b","v","mbh"})

def match_score(q, name):
    a, b = _norm(q), _norm(name)
    return len(a & b) / max(1, len(a | b))

def company(name, country=None, min_score=0.75):
    exact = json.loads(_get(f"{GLEIF}/lei-records?filter[entity.legalName]={urllib.parse.quote(name)}&page[size]=5") or '{"data":[]}')["data"]
    hits = [_lei(r) for r in exact] or gleif_search(name, country, size=10)
    for h in hits: h["match_score"] = round(match_score(name, h["legal_name"]), 2)
    if country: hits = [h for h in hits if h["country"] == country] or ([] if exact else hits)
    hits = sorted([h for h in hits if h["registration_status"] != "RETIRED"] or hits, key=lambda h: -h["match_score"])
    best = hits[0] if hits and hits[0]["match_score"] >= min_score else None
    res = {"query": name, "gleif": best, "gleif_alternatives": hits[1:]}
    if best: res["parents"] = gleif_parents(best["lei"])
    return res
