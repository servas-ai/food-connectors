"""BILLA + PENNY share the REWE commercetools 'product-discovery' API."""
import json, re, urllib.parse
from .base import Adapter
from ..http import get
from ..schema import Product, find_producer_id, parse_size_g, looks_like_ready_meal
NM = {'ENER-': 'kcal', 'PRO-': 'protein', 'FAT': 'fat', 'FASAT': 'satfat', 'CHOAVL': 'carbs', 'SUGAR-': 'sugar', 'FIBTG': 'fiber', 'SALTEQ': 'salt'}

class _Rewe(Adapter):
    base = ""; prefix = ""; categories = []
    def _p(self, r):
        pr = r.get("price") or {}; reg = pr.get("regular") or {}
        price = reg.get("value"); ppu = reg.get("perStandardizedQuantity")
        size = parse_size_g(f"{r.get('amount','')} {r.get('volumeLabelShort','')}")
        return Product(source=self.id, store=self.store, name=(r.get("name") or "").strip(),
            brand=(r.get("brand") or {}).get("name"), price_eur=price / 100 if price else None,
            unit_price_eur=ppu / 100 if ppu else None, unit=pr.get("baseUnitShort"), size_g=size,
            image_url=(r.get("images") or [None])[0], category=r.get("category"),
            source_url=f"{self.base}/produkte/{r.get('slug')}" if r.get("slug") else None, source_id=r.get("sku"))
    def search(self, q, limit=50):
        d = get(f"{self.base}/api/product-discovery/products?" + urllib.parse.urlencode({"term": q, "page": 0, "pageSize": min(limit, 100)}))
        res = [self._p(r) for r in d.get("results", [])]
        words = [w for w in re.findall(r"\w{3,}", q.lower())]
        txt = lambda p: (p.name + " " + (p.brand or "") + " " + (p.category or "")).lower()
        strict = [p for p in res if all(w in txt(p) for w in words)]
        if strict: return strict
        # BILLA search is fuzzy/stemmed (e.g. "suppe" -> "Suppentopf", "Hühnersuppe"); fall back to stem match, then raw ranking
        stem = [p for p in res if all(w[:max(4, len(w)-2)] in txt(p) for w in words)]
        return stem or res
    def listing(self, cat=None, pages=10):
        out = []
        for page in range(pages):
            path = f"categories/{cat}/products" if cat else "products"
            d = get(f"{self.base}/api/product-discovery/{path}?page={page}&pageSize=100")
            rs = d.get("results", []); out += [self._p(r) for r in rs]
            if len(rs) < 100: break
        return out
    def fetch(self, category="ready-meals", limit=500):
        items = []
        for c in (self.categories or [None]):
            try: items += self.listing(c)
            except Exception: pass
        seen, out = set(), []
        for p in items:
            if p.source_id in seen: continue
            seen.add(p.source_id)
            if category != "ready-meals" or looks_like_ready_meal(p.name, p.category): out.append(p)
        return out[:limit]
    def enrich(self, p):
        try: d = get(f"{self.base}/api/product-discovery/products/{p.source_id}")
        except Exception: return p
        txt = json.dumps(d, ensure_ascii=False)
        ai = (d.get("additionalInformation") or [{}])[-1] or {}
        fi = ai.get("foodInformation") or {}; pi = ai.get("productInformation") or {}
        n = {}
        for ni in fi.get("nutritionInfos", []):
            if ni.get("relationValue") != 100 or (n and ni.get("preparationGrade") != "Unzubereitet"): continue
            for x in ni.get("nutrients", []):
                k = NM.get(x.get("nutrientId"))
                if k and not (k == "kcal" and x["unit"]["symbol"] != "kcal"): n[k] = x["value"]
        p.nutrition_100g = n or p.nutrition_100g
        p.producer = pi.get("manufacturersAddress") or (pi.get("contactDetails") or {}).get("name") or p.producer
        p.producer_id = find_producer_id(txt); p.origin = d.get("countryOfOrigin") or p.origin
        eans = d.get("gtins") or d.get("eans") or []
        if eans: p.ean = str(eans[0])
        return p

class Billa(_Rewe):
    id = "billa"; store = "BILLA"; base = "https://shop.billa.at"; homepage = base
    categories = ["15395", "15390", "15391", "15232", "15233", "13842", "13969"]
    notes = "Public JSON API. Search ranking is weak, so `fetch` walks the ready-meal categories. BILLA Zustellung (home delivery to Linz) uses the same shop."

class Penny(_Rewe):
    id = "penny"; store = "PENNY"; base = "https://www.penny.at"; homepage = base
    categories = []
    notes = "Same REWE API as BILLA. Only the online assortment (~450 items) is listed; searchTerm is ignored, so search filters locally."
    def search(self, q, limit=50):
        words = re.findall(r"\w{3,}", q.lower())
        return [p for p in self.listing() if all(w in p.name.lower() for w in words)][:limit]
