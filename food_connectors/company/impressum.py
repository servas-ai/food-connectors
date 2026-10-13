"""Legal-notice (Impressum / Imprint / Note legali) adapter.
Austrian/German/EU law (§ 5 ECG, § 14 UGB, § 5 DDG, Art. 2250 c.c.) makes companies publish their register
number (FN/HRB/REA) and VAT id (UID) on their website. We fetch that public page (robots.txt respected,
1 req/s, no cookies/JS/login), extract the ids, and verify every VAT id against EU VIES. A record only counts
as verified when VIES says valid AND the VIES-registered name matches the company we looked for."""
import html, re, urllib.parse, urllib.robotparser
from .registries import _get, UA, now, vies_check, match_score

_LINK_HINT = re.compile(r"impressum|imprint|legal-?notice|note-?legali|mentions-?legales|colofon|offenlegung|legal|kontakt|contact|about", re.I)
_PATHS = ["/impressum", "/impressum/", "/de/impressum", "/at/impressum", "/imprint", "/en/imprint", "/impressum.html",
          "/legal-notice", "/note-legali", "/it/note-legali", "/kontakt", "/contact"]
VAT_RX = re.compile(r"\b(ATU(?:\s?\d){8}|DE\s?\d{3}\s?\d{3}\s?\d{3}|IT\s?\d{11}|FR\s?[0-9A-Z]{2}\s?\d{9}|NL(?:\s?\d){9}\s?B\s?\d{2}|BE\s?0?\d{3}\.?\d{3}\.?\d{3}"
                    r"|ES\s?[A-Z0-9]\d{7}[A-Z0-9]|PL\s?\d{10}|SI\s?\d{8}|CZ\s?\d{8,10}|SK\s?\d{10}|HU\s?\d{8}|DK\s?\d{8})\b")
FN_RX = re.compile(r"(?:\bFN|Firmenbuch(?:nummer|nr\.?)?)\s*[:.]?\s*(\d{1,6})\s?([a-zA-Z])\b")
HRB_RX = re.compile(r"\b(HR\s?[AB])\s?(\d{1,3}(?: \d{3})+|\d{2,7})\b(?:\s?([A-Z]{1,3})\b)?")
COURT_RX = re.compile(r"(?:Firmenbuchgericht|Registergericht|Handelsgericht|Landesgericht|Amtsgericht)\s*[:,]?\s*([A-ZÄÖÜ][\wäöüß .-]{2,40}?)(?=[,;\n]|\s{2}|$)")

def _robots_ok(base, url):
    rp = urllib.robotparser.RobotFileParser()
    try:
        t = _get(base + "/robots.txt", tries=1, timeout=12)
        rp.parse((t or "").splitlines())
        return rp.can_fetch(UA, url)
    except Exception:
        return True  # unreachable robots.txt = no restriction (RFC 9309 §2.3.1.3 for 4xx)

def _text(h):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", h)
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))

def _fetch(url):
    try: return _get(url, tries=1, timeout=20)
    except Exception: return None

def find_imprint(domain):
    """Return (url, html) of the legal-notice page for a domain, or (None, None)."""
    base = domain if domain.startswith("http") else "https://" + domain
    base = base.rstrip("/"); p = urllib.parse.urlparse(base); base = f"{p.scheme}://{p.netloc}"
    home = _fetch(base + "/") if _robots_ok(base, base + "/") else None
    cands = []
    if home:
        for href, label in re.findall(r'(?is)<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', home):
            lab = _text(label).strip()
            if re.search(r"impressum|imprint|legal notice|note legali|mentions l|colofon|offenlegung", lab + " " + href, re.I):
                u = urllib.parse.urljoin(base + "/", html.unescape(href))
                if urllib.parse.urlparse(u).netloc.split(":")[0].endswith(p.netloc.replace("www.", "")) and u not in cands: cands.append(u)
    cands += [base + x for x in _PATHS if base + x not in cands]
    for u in cands[:8]:
        if not _robots_ok(base, u): continue
        h = _fetch(u)
        if h and (VAT_RX.search(_text(h)) or FN_RX.search(_text(h))): return u, h
    if home and (VAT_RX.search(_text(home)) or FN_RX.search(_text(home))): return base + "/", home
    return None, None

def impressum(domain, name=None, verify=True):
    """Extract FN/HRB/UID from a company's public legal notice and verify UIDs via EU VIES.
    If `name` is given, `best` is the VIES-valid UID whose registered name matches it (score >= 0.5)."""
    url, h = find_imprint(domain)
    out = {"domain": domain, "imprint_url": url, "fetched_at": now(), "uids": [], "fn": [], "hrb": [], "court": None, "best": None}
    if not url: out["error"] = "no imprint page with register/VAT ids found (or robots-disallowed / JS-only)"; return out
    t = _text(h)
    out["fn"] = sorted({f"FN {a}{b.lower()}" for a, b in FN_RX.findall(t)})
    out["hrb"] = sorted({" ".join(x for x in (m[0].replace(" ", ""), m[1].replace(" ", ""), m[2] if m[2] not in ("AG", "UST", "USt") else "") if x) for m in HRB_RX.findall(t)})
    c = COURT_RX.search(t); out["court"] = c.group(1).strip() if c else None
    vats = []
    for v in VAT_RX.findall(t):
        v = re.sub(r"[\s.]", "", v)
        if v not in vats: vats.append(v)
    for v in vats[:6]:
        rec = {"uid": v}
        if verify:
            try:
                d = vies_check(v)
                rec.update(valid=bool(d.get("valid")), vies_name=(d.get("name") if d.get("name") not in ("---", "") else None),
                           vies_address=(d.get("address") if d.get("address") not in ("---", "") else None), checked_at=d.get("requestDate"))
            except Exception as e:
                rec.update(valid=None, error=str(e)[:120])
            if name and rec.get("vies_name"): rec["name_match"] = round(match_score(name, rec["vies_name"]), 2)
        out["uids"].append(rec)
    if name:
        ok = [u for u in out["uids"] if u.get("valid") and (u.get("name_match") or 0) >= 0.5]
        # DE VIES returns no name: accept a valid DE id only if the company name appears verbatim on the page
        if not ok:
            ok = [u for u in out["uids"] if u.get("valid") and not u.get("vies_name") and _name_on_page(name, t)]
            for u in ok: u["name_match"] = "on_page"
        out["best"] = max(ok, key=lambda u: u["name_match"] if isinstance(u["name_match"], float) else 0.5) if ok else None
    out["source"] = "public legal notice + EU VIES"
    return out

def _name_on_page(name, t):
    core = re.sub(r"\b(GmbH|AG|KG|S\.?p\.?A\.?|srl|S\.r\.l\.|& Co\.?)\b", "", name, flags=re.I).strip(" ,.&")
    return len(core) >= 4 and core.lower() in t.lower()
