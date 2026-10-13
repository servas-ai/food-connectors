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
    mk("denns", "denn's BioMarkt", "https://www.denns-biomarkt.at", "Marketing/info site (Sanity CMS). No product listing, no usable sitemap (robots points to biomarkt.de sitemap → 404), no public product JSON/API. Austrian branches via osm-stores. Catalog-only."),
    mk("nah-frisch", "Nah&Frisch", "https://www.nahundfrisch.at", "Franchise info site; no webshop/product API. Branches via osm-stores. Catalog-only."),
    mk("adeg", "ADEG", "https://www.adeg.at", "REWE group franchise portal. Sitemap = pages/news/recipes only; no product catalog or online shop. Branches via osm-stores."),
    mk("unimarkt-shop", "Unimarkt (UNIONLINE Shop)", "https://shop.unimarkt.at", "CLOSED, verified 2026-10-13: shop.unimarkt.at answers 200 but every category/product slug (/fertiggerichte, /suppen, /snacks-fertiggerichte, ...) 302-redirects to / which shows only the splash 'UNIONLINE hat seinen Service eingestellt – Vielen Dank für Ihre Treue' (/upload/content/schliessung/info.png). Shop closed end of Feb 2024 (cash.at 2024-02-23); Unimarkt left retail Feb/Mar 2026 (ooe.ORF.at 2026-03-14: ~90 stores closed, REWE/ADEG took 21, Spar 23, Nah&Frisch 2). Sitemap google.cfm still lists 1312 dead slugs; core.js ajaxGateway has only cart/merkliste actions (no product list); /suche/ returns 403 (not retried). No live product, price or photo source exists. Historic prices: `unimarkt` (heisse-preise dump)."),
    mk("wokostswas", "wokostswas.at", "https://wokostswas.at", "Price comparison site. HTML only."),
]
