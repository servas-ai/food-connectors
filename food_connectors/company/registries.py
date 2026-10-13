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

import unicodedata

_LEGAL = {"gmbh","ag","kg","co","und","the","bv","b","v","mbh","m","h","gesmbh","gesellschaft","gesellschaftmbh",
          "nv","n","sa","s","a","srl","r","l","spa","p","sp","z","o","oo","ltd","limited","ohg","og","eu","se","kgaa",
          "inc","llc","sl","sas","sarl","bvba","as","oy","ab","aktiengesellschaft","kommanditgesellschaft","offene"}

def _fold(x):
    """lowercase, strip diacritics; ae/oe/ue -> a/o/u so 'Schär' == 'SCHAER' == 'Schar'."""
    x = unicodedata.normalize("NFKD", (x or "").lower().replace("ß", "ss"))
    x = "".join(c for c in x if not unicodedata.combining(c))
    return re.sub(r"(?<=[a-z])(ae|oe|ue)", lambda m: m.group(1)[0], x)

def _norm(x):
    return set(t for t in re.findall(r"[a-z0-9]+", _fold(x)) if t not in _LEGAL)

_FORMS = [  # legal-form families; AG == SpA == SA == NV (joint-stock), GmbH == srl == B.V. == s.r.o. ...
    ("stock", r"\b(ag|aktiengesellschaft|s\.?\s?p\.?\s?a|per azioni|n\.?\s?v|s\.?\s?a)\b\.?"),
    ("ltd", r"\b(gmbh|ges\.?\s?m\.?\s?b\.?\s?h|gesellschaft\s+m\.?\s?b\.?\s?h|mbh|s\.?\s?r\.?\s?l|b\.?\s?v|s\.?\s?r\.?\s?o|sp\.?\s?z\.?\s?o\.?\s?o|ltd|limited|s\.?\s?l)\b\.?"),
    ("kg", r"\b(kg|kommanditgesellschaft)\b"), ("se", r"\bse\b"), ("og", r"\b(og|ohg)\b"), ("egen", r"\begen\b"),
]

def _forms(x):
    f = _fold(x)
    return {k for k, rx in _FORMS if re.search(rx, f)}

def match_score(q, name):
    """Token Jaccard on legal-form-agnostic names; capped at 0.6 when both names carry legal forms
    from different families (e.g. 'Ehrmann GmbH' vs 'Ehrmann SE' = different entity/time)."""
    a, b = _norm(q), _norm(name)
    s = len(a & b) / max(1, len(a | b))
    fa, fb = _forms(q), _forms(name)
    if fa and fb and not (fa & fb): s = min(s, 0.6)
    return s

def _variants(name):
    """GLEIF fulltext is diacritic-sensitive: try original, plain ASCII (ö->o) and German transliteration (ö->oe)."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    de = name
    for a, b in (("ä","ae"),("ö","oe"),("ü","ue"),("Ä","Ae"),("Ö","Oe"),("Ü","Ue"),("ß","ss")): de = de.replace(a, b)
    core = re.sub(r"[,.]?\s*(GmbH|AG|KG|Ges\.?m\.?b\.?H\.?|Gesellschaft m\.?b\.?H\.?|m\.b\.H\.|NV|N\.V\.|B\.V\.|S\.p\.A\.|srl|SL\.?|& Co\.? ?KG)\b\.?", "", plain, flags=re.I).strip(" ,.&")
    core_de = re.sub(r"[,.]?\s*(GmbH|AG|KG|NV|SpA|srl)\b\.?", "", de, flags=re.I).strip(" ,.&")
    out = []
    for v in (name, plain, de, core, core_de):
        if v and v not in out: out.append(v)
    return out

def company(name, country=None, min_score=0.85):
    """Resolve a company name to one GLEIF record. Strict: best hit needs match_score >= min_score on the
    legal-form-agnostic, diacritic-folded name, and (if country given) the legal address must be in that country.
    Search order: exact legalName, then fulltext for each spelling variant until a qualifying hit appears."""
    seen, hits = set(), []
    def add(recs):
        for r in recs:
            h = r if "lei" in r else _lei(r)
            if h["lei"] in seen: continue
            seen.add(h["lei"]); h["match_score"] = round(match_score(name, h["legal_name"]), 2); hits.append(h)
    def ok(h): return h["match_score"] >= min_score and (not country or h["country"] == country)
    add(json.loads(_get(f"{GLEIF}/lei-records?filter[entity.legalName]={urllib.parse.quote(name)}&page[size]=5") or '{"data":[]}')["data"])
    for v in _variants(name):
        if any(ok(h) for h in hits): break
        add(gleif_search(v, country, size=10))
    cand = [h for h in hits if (not country or h["country"] == country)]
    cand = sorted([h for h in cand if h["registration_status"] != "RETIRED"] or cand, key=lambda h: -h["match_score"])
    best = cand[0] if cand and ok(cand[0]) else None
    res = {"query": name, "gleif": best, "gleif_alternatives": [h for h in sorted(hits, key=lambda h: -h["match_score"]) if h is not best][:8]}
    if best: res["parents"] = gleif_parents(best["lei"])
    return res
