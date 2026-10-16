"""robots.txt gate (polite_http): disallowed → no network call; allowed passes; RFC 9309 unreachable handling; 1 s/host."""
import io, os, sys, urllib.error, urllib.request, pytest

from food_connectors import polite as P

class FakeNet:
    def __init__(self, robots): self.robots, self.calls = robots, []
    def __call__(self, req, *a, **kw):
        url = req.full_url if isinstance(req, urllib.request.Request) else req
        self.calls.append(url)
        if url.endswith('/robots.txt'):
            r = self.robots
            if isinstance(r, int): raise urllib.error.HTTPError(url, r, 'x', {}, io.BytesIO(b''))
            if isinstance(r, Exception): raise r
            return io.BytesIO(r.encode())
        return io.BytesIO(b'ok')

@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    P._robots.clear(); P._last.clear(); P.BLOCKED.clear(); monkeypatch.setattr(P, 'MIN_INTERVAL', 0.0)

INTERSPAR = "User-agent: *\nDisallow: /shop/\n"

def test_interspar_product_disallowed_no_request(monkeypatch):
    net = FakeNet(INTERSPAR); monkeypatch.setattr(P, '_ORIG_URLOPEN', net)
    u = 'https://www.interspar.at/shop/lebensmittel/dr-oetker-tradizionale-diavola/p/7575327'
    with pytest.raises(P.RobotsDisallowed): P.polite_get(u)
    assert net.calls == ['https://www.interspar.at/robots.txt'] and P.BLOCKED[0][0] == u

def test_allowed_url_goes_through(monkeypatch):
    net = FakeNet("User-agent: *\nDisallow: /wp-admin/\n"); monkeypatch.setattr(P, '_ORIG_URLOPEN', net)
    assert P.polite_get('https://kernbeisser.at/agbs/') == b'ok'
    assert P.polite_get('https://kernbeisser.at/') == b'ok'
    assert net.calls.count('https://kernbeisser.at/robots.txt') == 1  # cached

def test_ua_specific_group(monkeypatch):
    net = FakeNet("User-agent: food-connectors\nDisallow: /\n\nUser-agent: *\nAllow: /\n"); monkeypatch.setattr(P, '_ORIG_URLOPEN', net)
    with pytest.raises(P.RobotsDisallowed): P.polite_get('https://example.org/x')

@pytest.mark.parametrize('robots,ok', [(404, True), (403, True), (401, True), (500, False), (503, False), (urllib.error.URLError('down'), False)])
def test_rfc9309_unreachable(monkeypatch, robots, ok):
    net = FakeNet(robots); monkeypatch.setattr(P, '_ORIG_URLOPEN', net)
    if ok: assert P.polite_get('https://h.example/p') == b'ok'
    else:
        with pytest.raises(P.RobotsDisallowed): P.polite_get('https://h.example/p')
        assert net.calls == ['https://h.example/robots.txt']

def test_rate_limit_per_host(monkeypatch):
    net = FakeNet("User-agent: *\nAllow: /\n"); monkeypatch.setattr(P, '_ORIG_URLOPEN', net); monkeypatch.setattr(P, 'MIN_INTERVAL', 0.3)
    import time; t = time.monotonic()
    for _ in range(3): P.polite_get('https://r.example/a')
    assert time.monotonic() - t >= 0.85  # robots + 3 requests on one host ≥ 3 × 0.3 s

def test_install_routes_urlopen_and_curl(monkeypatch):
    net = FakeNet(INTERSPAR); monkeypatch.setattr(P, '_ORIG_URLOPEN', net)
    import subprocess
    orig_u, orig_r = urllib.request.urlopen, subprocess.run
    ran = []
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: ran.append(a))
    monkeypatch.setattr(P, '_installed', False)
    try:
        P.install()
        with pytest.raises(P.RobotsDisallowed): urllib.request.urlopen('https://www.interspar.at/shop/x')
        with pytest.raises(P.RobotsDisallowed): subprocess.run(['curl', '-s', 'https://www.interspar.at/shop/y'])
        assert ran == []
    finally:
        urllib.request.urlopen = orig_u; subprocess.run = orig_r; P._installed = False
