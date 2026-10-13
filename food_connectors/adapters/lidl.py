import urllib.parse
from .base import Adapter
from ..http import get
from ..schema import Product, parse_size_g
class Lidl(Adapter):
    id = "lidl"; store = "Lidl"; homepage = "https://www.lidl.at"
    notes = "lidl.at search API (q/api/search). Prices and images only; no nutrition online for most food items."
    def search(self, q, limit=50):
        d = get("https://www.lidl.at/q/api/search?" + urllib.parse.urlencode({"q": q, "fetchsize": min(limit, 48), "locale": "de_AT", "assortment": "AT", "version": "v2.0.0"}))
        out = []
        for it in d.get("items", []):
            g = (it.get("gridbox") or {}).get("data") or {}
            pr = g.get("price") or {}
            out.append(Product(source=self.id, store=self.store, name=g.get("fullTitle") or g.get("title") or "",
                brand=(g.get("brand") or {}).get("name"), price_eur=pr.get("price"),
                size_g=parse_size_g((pr.get("packaging") or {}).get("text")), image_url=g.get("image"), category=g.get("category"),
                source_url="https://www.lidl.at" + g["canonicalUrl"] if g.get("canonicalUrl") else None, source_id=it.get("code")))
        return out
