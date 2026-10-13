"""heisse-preise.io: open price dump for Austrian chains (billa, spar, hofer, dm, mpreis, unimarkt, penny, ...)."""
import json, os, re, time
from .base import Adapter
from ..http import get
from ..schema import Product, looks_like_ready_meal
URL = "https://heisse-preise.io/data/latest-canonical.json"
CACHE = os.path.expanduser("~/.cache/food-connectors/heisse-preise.json")
_DATA = None
def data(max_age_h=12):
    global _DATA
    if _DATA is None:
        if not os.path.exists(CACHE) or time.time() - os.path.getmtime(CACHE) > max_age_h * 3600:
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            b = get(URL, raw=True, timeout=300); open(CACHE, "wb").write(b)
        _DATA = json.load(open(CACHE))
    return _DATA
STORE_NAMES = {"billa": "BILLA", "spar": "SPAR/INTERSPAR", "hofer": "HOFER", "dm": "dm", "mpreis": "MPREIS", "unimarkt": "Unimarkt", "penny": "PENNY", "lidl": "Lidl"}
def to_product(x, src):
    ph = x.get("priceHistory") or [{}]
    return Product(source=src, store=STORE_NAMES.get(x.get("store"), x.get("store")), name=(x.get("name") or "").strip(),
        price_eur=x.get("price"), size_g=(x.get("quantity") if x.get("unit") in ("g", "ml") else None), unit=x.get("unit"),
        source_url=x.get("url"), source_id=str(x.get("id")), category=x.get("category"),
        extra={"price_date": ph[0].get("date"), "bio": x.get("bio")})
class HeissePreise(Adapter):
    id = "heisse-preise"; store = "heisse-preise.io"; homepage = "https://heisse-preise.io"
    notes = "~200 MB daily dump, cached 12 h in ~/.cache/food-connectors. Billa/Spar are current; Hofer/dm/MPreis/Unimarkt can be stale. Check extra.price_date."
    chain = None
    def search(self, q, limit=50):
        words = re.findall(r"\w{3,}", q.lower()); out = []
        for x in data():
            if self.chain and x.get("store") != self.chain: continue
            if all(w in (x.get("name") or "").lower() for w in words):
                out.append(to_product(x, self.id))
                if len(out) >= limit: break
        return out
    def fetch(self, category="ready-meals", limit=5000):
        out = []
        for x in data():
            if self.chain and x.get("store") != self.chain: continue
            if looks_like_ready_meal(x.get("name") or ""): out.append(to_product(x, self.id))
        return out[:limit]
def chain_adapter(cid, label, status, notes):
    return type(cid.title(), (HeissePreise,), {"id": cid, "store": label, "chain": cid, "status": status, "notes": notes, "homepage": f"https://www.{cid}.at"})
Spar = chain_adapter("spar", "SPAR/INTERSPAR", "live", "Prices from heisse-preise (Spar search API). Product pages and nutrition on interspar.at sit behind Cloudflare, so you need a real browser (search URL https://www.interspar.at/shop/lebensmittel/suche?q=). Images: cdn.spar.at.")
Hofer = chain_adapter("hofer", "HOFER", "stale", "roksh/hofer online shop closed; the heisse-preise data may be old. For current Good Choice data use hofer.at/de/sortiment pages in a browser.")
Dm = chain_adapter("dm", "dm", "stale", "dm.at product API needs a browser session (bot protection). heisse-preise data may be old.")
Mpreis = chain_adapter("mpreis", "MPREIS", "stale", "Tyrol only, not in Linz. heisse-preise data.")
Unimarkt = chain_adapter("unimarkt", "Unimarkt", "stale", "Unimarkt (Upper Austria) online shop is closed; heisse-preise history only.")
