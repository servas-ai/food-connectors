from __future__ import annotations
from ..schema import Product, looks_like_ready_meal

READY_MEAL_QUERIES = ["fertiggericht", "gulasch", "chili con carne", "eintopf", "suppentopf", "lasagne", "curry",
    "risotto", "geschnetzeltes", "ripperl", "menü", "bowl", "linseneintopf", "krautfleckerl", "spätzle", "gnocchi",
    "tortellini", "pasta", "huhn", "hendl", "nasi goreng", "tikka masala", "schweinsbraten", "knödel"]

class Adapter:
    id = "base"; store = "?"; homepage = ""
    status = "live"          # live | stale | browser-only | catalog-only
    notes = ""
    def search(self, q: str, limit: int = 50) -> list[Product]:
        raise NotImplementedError
    def fetch(self, category: str = "ready-meals", limit: int = 500) -> list[Product]:
        if category != "ready-meals":
            return self.search(category, limit)
        seen, out = set(), []
        for q in READY_MEAL_QUERIES:
            try: res = self.search(q, 60)
            except Exception: continue
            for p in res:
                k = p.source_id or p.name
                if k in seen or not looks_like_ready_meal(p.name, p.category): continue
                seen.add(k); out.append(p)
                if len(out) >= limit: return out
        return out
    def enrich(self, p: Product) -> Product:
        """Fill nutrition/producer from a detail endpoint when the adapter has one."""
        return p
    def info(self):
        return {"id": self.id, "store": self.store, "homepage": self.homepage, "status": self.status, "notes": self.notes}
