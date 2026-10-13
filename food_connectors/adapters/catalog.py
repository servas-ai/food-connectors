"""Catalog-only entries: sources we looked at that have no usable public API (yet)."""
from .base import Adapter
class _Cat(Adapter):
    status = "catalog-only"
    def search(self, q, limit=50): return []
    def fetch(self, category="ready-meals", limit=0): return []
def mk(i, s, h, n): return type(i.replace("-", "_"), (_Cat,), {"id": i, "store": s, "homepage": h, "notes": n})
CATALOG = [
    mk("foodora-market", "foodora market (Dmart)", "https://www.foodora.at", "Quick commerce in Linz. App API needs location and session tokens; not scraped."),
    mk("mjam", "mjam (now foodora)", "https://www.mjam.net", "Redirects to foodora."),
    mk("lieferando-shops", "Lieferando Shops", "https://www.lieferando.at", "Lists restaurants and some convenience shops. Product APIs are tokenized; no grocery nutrition."),
    mk("bio-kistl", "Biohof Achleitner / Bio-Kistl OÖ", "https://www.biohof.at", "Organic box delivery in Upper Austria. Shop HTML only, few ready meals."),
    mk("fittogo", "Fit to Go", "https://www.fittogo.at", "Meal-prep vending/delivery. Scrape the HTML menu (see fertiggerichte project)."),
    mk("adeg", "ADEG", "https://www.adeg.at", "REWE group; no online shop."),
    mk("wokostswas", "wokostswas.at", "https://wokostswas.at", "Price comparison site. HTML only."),
]
