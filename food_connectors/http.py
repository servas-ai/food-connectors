import json, time, urllib.request, urllib.error
from .polite import polite_urlopen, RobotsDisallowed  # hard robots.txt + 1 s/host gate
UA = "Mozilla/5.0 (X11; Linux x86_64) food-connectors/0.1 (+https://github.com/servas-ai/food-connectors)"

def get(url, headers=None, timeout=30, retries=2, raw=False):
    h = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.8"}
    h.update(headers or {})
    last = None
    for i in range(retries + 1):
        try:
            with polite_urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except RobotsDisallowed:
            raise
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 404): break
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise last
