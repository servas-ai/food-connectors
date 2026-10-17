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
def spar_cdn_image(article_id):
    """Public Spar/Interspar product image CDN (no Cloudflare on this host). Verified 2026-10-13."""
    if not article_id: return None
    return f"https://cdn1.interspar.at/cachableservlets/articleImage.dam/at/{article_id}/dt_main.jpg"

def to_product(x, src):
    ph = x.get("priceHistory") or [{}]
    img = spar_cdn_image(x.get("id")) if x.get("store") == "spar" else None
    return Product(source=src, store=STORE_NAMES.get(x.get("store"), x.get("store")), name=(x.get("name") or "").strip(),
        price_eur=x.get("price"), size_g=(x.get("quantity") if x.get("unit") in ("g", "ml") else None), unit=x.get("unit"),
        source_url=x.get("url"), source_id=str(x.get("id")), category=x.get("category"), image_url=img,
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
Spar = chain_adapter("spar", "SPAR/INTERSPAR", "live", "Prices from heisse-preise (Spar search API). Product pages and nutrition on interspar.at sit behind Cloudflare (search URL https://www.interspar.at/shop/lebensmittel/suche?q=). Images: public CDN cdn1.interspar.at/cachableservlets/articleImage.dam/at/{id}/dt_main.jpg (HEAD-verified 2026-10-13; 227/228 ready-meal enrichments).")
Hofer = chain_adapter("hofer", "HOFER", "stale", "roksh/hofer online shop closed; heisse-preise has no 2026 Hofer dates (latest ~2025-10). hofer.at was Akamai-blocked for bots until 2026-10-16; since 2026-10-17 the public sitemap + product pages are served (robots allow) → live prices/packshots via `hofer-shop`. Photos: enrich via Open Food Facts (strict brand+token match) + public Aldi CDN dm.emea.cms.aldi.cx (brandfam titles); see fertiggerichte-daten scripts/enrich_hofer_images.py. No Spar-like article CDN id in heisse for Hofer.")
Dm = chain_adapter("dm", "dm", "stale", "heisse-preise dm snapshot (may be old). Live dm data: adapter `dm` (dm_shop.py).")
Dm.id = "dm-heisse"
Mpreis = chain_adapter("mpreis", "MPREIS", "stale", "Tyrol only, not in Linz. heisse-preise data.")
Unimarkt = chain_adapter("unimarkt", "Unimarkt", "stale", "Historic only: UNIONLINE shop closed 02/2024 (verified 2026-10-13, see catalog `unimarkt-shop`) and Unimarkt exited retail 02-03/2026 (stores closed or rebranded ADEG/Spar/Nah&Frisch). heisse-preise 2023/24 prices only; no live source.")
