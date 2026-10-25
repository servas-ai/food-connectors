import json, pathlib
from food_connectors.adapters import kumitzberg as K

FX = pathlib.Path(__file__).parent / "fixtures"
SHOP = json.loads((FX / "kumitzberg_products.json").read_text())["products"]
REH = (FX / "kumitzberg_rehragout.html").read_text()


def test_filter_meals():
    names = sorted(K.to_product(p).name for p in SHOP if K.is_meal(p))
    assert names == ["Kaspressknödel", "Rehragout im Glas", "Schweinsbraten vom Schopf, fertig gebraten",
                     "Sous-Vide Spareribs „Mamasita“", "Tirolerknödel"]


def test_parse_rehragout():
    p = K.product("rehragout-im-glas-380g", SHOP, REH)
    assert p.store == "Online: Kumitzberg" and p.price_eur == 12.9 and p.size_g == 380.0 and p.unit_price_eur == 33.95
    assert p.nutrition_100g == {"kcal": 121.0, "fat": 6.8, "satfat": 0.9, "carbs": 3.9, "sugar": 1.4, "protein": 11.0, "salt": 1.4}
    assert p.extra["ingredients"].startswith("30 % Rehfleisch (AT)") and "SELLERIE" in p.extra["ingredients"]
    assert p.ean is None and p.image_url.startswith("https://cdn.shopify.com/") and "rehragout" in p.image_url


def test_excluded_and_size():
    assert K.product("gebackene-leberknodel", SHOP, "") is None and K.product("leberkaese-500g-rauchofen", SHOP, "") is None
    assert K.product("selchschopf", SHOP, "") is None and K.product("nope", SHOP, "") is None
    sr = next(p for p in SHOP if p["handle"] == "sous-vide-spareribs")
    assert K.size_g(sr) == (1200.0, True)
