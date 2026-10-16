"""Hard robots.txt + rate-limit gate for every outgoing HTTP request (orch 2026-10-16 21:59).

- robots.txt per scheme+host, fetched once and cached (urllib.robotparser rules, UA-specific group plus '*').
- RFC 9309 §2.3.1: robots.txt 2xx → parse; 4xx (incl. 401/403/404) → no restrictions (allow);
  5xx / network error / timeout → complete disallow (conservative) until the cache entry expires.
- Disallowed URLs raise RobotsDisallowed BEFORE any request is sent (and are logged).
- At most one request per host per MIN_INTERVAL seconds (default 1.0), robots.txt fetch included.

Use polite_get(url) / polite_urlopen(req) directly, or call install() once at process start: it routes
urllib.request.urlopen, requests (Session.request), httpx (Client.send) and subprocess.run(['curl', …]) through the gate."""
import logging, threading, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser, os

log = logging.getLogger('polite_http')
UA = os.environ.get('POLITE_UA', 'Mozilla/5.0 (X11; Linux x86_64) food-connectors/0.1 (+https://github.com/servas-ai/food-connectors)')
ROBOTS_UA = os.environ.get('POLITE_ROBOTS_UA', 'food-connectors')
MIN_INTERVAL = float(os.environ.get('POLITE_MIN_INTERVAL', '1.0'))
CACHE_TTL = 24 * 3600
_ORIG_URLOPEN = urllib.request.urlopen
_lock = threading.Lock(); _last = {}; _robots = {}
BLOCKED = []  # (url, reason) log for callers/tests

class RobotsDisallowed(Exception):
    pass

def _wait(host):
    with _lock:
        now = time.monotonic(); w = _last.get(host, -1e9) + MIN_INTERVAL - now
        _last[host] = max(now, now + w) if w > 0 else now
    if w > 0: time.sleep(w)

class _Rules:
    def __init__(self, mode, rp=None): self.mode, self.rp, self.t = mode, rp, time.time()
    def allowed(self, url, ua):
        if self.mode == 'allow': return True
        if self.mode == 'deny': return False
        # UA-specific group (our robots token and the full UA string) and '*' via robotparser's fallback
        return self.rp.can_fetch(ROBOTS_UA, url) and self.rp.can_fetch(ua, url)

def _fetch_robots(base):
    url = base + '/robots.txt'
    _wait(urllib.parse.urlsplit(base).netloc)
    try:
        with _ORIG_URLOPEN(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=20) as r:
            body = r.read().decode('utf-8', 'ignore')
        rp = urllib.robotparser.RobotFileParser(); rp.parse(body.splitlines()); return _Rules('parse', rp)
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500: return _Rules('allow')
        log.warning('robots.txt %s → HTTP %s: disallow all (RFC 9309)', url, e.code); return _Rules('deny')
    except Exception as e:
        log.warning('robots.txt %s unreachable (%s): disallow all (RFC 9309)', url, e); return _Rules('deny')

def check(url, ua=None):
    """Raise RobotsDisallowed if robots.txt forbids url; non-http(s) URLs pass."""
    s = urllib.parse.urlsplit(url)
    if s.scheme not in ('http', 'https') or not s.netloc: return
    base = f'{s.scheme}://{s.netloc}'
    with _lock: r = _robots.get(base)
    if r is None or time.time() - r.t > CACHE_TTL:
        r = _fetch_robots(base)
        with _lock: _robots[base] = r
    if not r.allowed(url, ua or UA):
        BLOCKED.append((url, r.mode)); log.warning('robots.txt disallows %s (%s) – request not sent', url, r.mode)
        raise RobotsDisallowed(url)

def gate(url, ua=None):
    check(url, ua); _wait(urllib.parse.urlsplit(url).netloc)

def polite_urlopen(req, *a, **kw):
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    ua = req.get_header('User-agent') if isinstance(req, urllib.request.Request) else None
    gate(url, ua)
    return _ORIG_URLOPEN(req, *a, **kw)

def polite_get(url, headers=None, timeout=30):
    """GET url through the gate; returns bytes."""
    h = {'User-Agent': UA}; h.update(headers or {})
    with polite_urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read()

_installed = False
def install():
    """Route urllib / requests / httpx / subprocess curl through the gate (idempotent)."""
    global _installed
    if _installed: return
    _installed = True
    urllib.request.urlopen = polite_urlopen
    try:
        import requests
        _orig_req = requests.Session.request
        def _req(self, method, url, *a, **kw):
            gate(url, (kw.get('headers') or {}).get('User-Agent') or self.headers.get('User-Agent'))
            return _orig_req(self, method, url, *a, **kw)
        requests.Session.request = _req
    except ImportError: pass
    try:
        import httpx
        _orig_send = httpx.Client.send
        def _send(self, request, *a, **kw):
            gate(str(request.url), request.headers.get('user-agent')); return _orig_send(self, request, *a, **kw)
        httpx.Client.send = _send
    except ImportError: pass
    import subprocess
    _orig_run = subprocess.run
    def _run(args, *a, **kw):
        if isinstance(args, (list, tuple)) and args and os.path.basename(str(args[0])) in ('curl', 'wget'):
            ua = None
            for i, x in enumerate(args):
                if str(x) in ('-A', '--user-agent') and i + 1 < len(args): ua = str(args[i + 1])
            for x in args:
                if str(x).startswith(('http://', 'https://')): gate(str(x), ua)
        elif isinstance(args, str) and args.lstrip().startswith(('curl ', 'wget ')):
            import re
            for u in re.findall(r'https?://[^\s\'"]+', args): gate(u)
        return _orig_run(args, *a, **kw)
    subprocess.run = _run
