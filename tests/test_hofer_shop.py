"""Offline tests for the hofer-shop adapter (fixture = re-encoded __NUXT_DATA__ of a real hofer.at product page, 2026-10-17)."""
import os
from food_connectors.adapters.hofer_shop import parse_page, to_product, is_ready_meal, slug_candidate, PRODUCT_RE, HoferShop
from food_connectors.adapters import ADAPTERS
from food_connectors.schema import Product

FX = os.path.join(os.path.dirname(__file__), "fixtures", "hofer_product_745927002.html")
URL = "https://www.hofer.at/produkt/arnold-soerensen-1882-thunfisch-reis-korea-suess-wuerzig-000000000745927002"

def test_parse_product_page():
    p = to_product(parse_page(open(FX).read(), URL), URL)
    assert p.source == "hofer-shop" and p.store == "HOFER"
    assert p.price_eur == 1.99 and p.unit_price_eur == 12.44 and p.unit == "kg"
    assert p.size_g == 160.0 and p.source_id == "000000000745927002"
    assert p.ean is None and p.nutrition_100g == {}  # hofer.at publishes neither — never estimated
    assert p.image_url.startswith("https://dm.emea.cms.aldi.cx/") and "{width}" not in p.image_url and "/600/" in p.image_url
    assert p.extra["on_sale_date"] == "2026-10-16" and "Tuna" in p.extra["ingredients"]
    assert is_ready_meal(p)

def test_sku_mismatch_returns_none():
    assert parse_page(open(FX).read(), "https://www.hofer.at/produkt/other-000000000000000001") is None

def test_slug_prefilter_and_meal_filter():
    assert slug_candidate("https://www.hofer.at/produkt/primana-xxl-lasagne-000000000000123456")
    assert not slug_candidate("https://www.hofer.at/produkt/milsani-emmentaler-scheiben-000000000000106972")
    assert PRODUCT_RE.search("https://www.hofer.at/produkt/a-b-000000000000106972").group(2) == "000000000000106972"
    mk = lambda n: Product(source="hofer-shop", store="HOFER", name=n)
    assert is_ready_meal(mk("Pizz'Ah Air Fryer Pizza, Schinken"))
    assert is_ready_meal(mk("Knorr Namdong Noodles Cup, Namdong Beef"))
    assert not is_ready_meal(mk("Cucina Nobile Pesto alla Genovese"))
    assert not is_ready_meal(mk("Kania Gulasch Gewürz"))
    assert not is_ready_meal(mk("Gourmet Finest Cuisine Chili-Gewu\u0308rzmu\u0308hle, Red Chili-Mix"))  # NFD from hofer.at
    assert not is_ready_meal(mk("Sonnhof Maishendl-Geschnetzeltes")) and not is_ready_meal(mk("Back Family Schokolinsen bunt"))

def test_registered():
    assert isinstance(ADAPTERS["hofer-shop"], HoferShop) and ADAPTERS["hofer-shop"].status == "live"

def test_raw_meat_and_weight_article():
    p = Product(source="hofer-shop", store="HOFER", name="Sonnhof Rindsgulasch",
                extra={"ingredients": "100% Rindfleisch", "usage": "Vor dem Verzehr gut durcherhitzen. Rohes Fleisch gekühlt lagern"})
    assert not is_ready_meal(p)  # 'Rindsgulasch' at Hofer = raw diced beef, not a heat-up meal
    node = {"sku": "000000000000510738", "name": "Rindsgulasch", "brandName": "SONNHOF", "sellingSize": "ungefähr 0,5 kg/Stück",
            "weightType": "1", "price": {"amount": 1299, "amountRelevant": 650, "comparison": 1299, "comparisonDisplay": "€ 12,99/1 kg"}, "assets": []}
    q = to_product(node)
    assert q.price_eur == 6.5 and q.unit_price_eur == 12.99 and q.extra["weight_article"]
