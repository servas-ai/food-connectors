import json, pathlib
from food_connectors.adapters import wagyuhof as W

FX = pathlib.Path(__file__).parent / "fixtures"
SHOP = json.loads((FX / "wagyuhof_frischglas_products.json").read_text())["products"]
PAGE = lambda h: (FX / f"wagyuhof_{h}.html").read_text()


def test_filter_meals():
    assert sorted(p["handle"] for p in SHOP if W.is_meal(p)) == ["wagyu-beuschel", "wagyu-gulasch", "wagyu-ragout", "wagyu-rouladen"]


def test_parse_gulasch():
    p = W.to_product(next(x for x in SHOP if x["handle"] == "wagyu-gulasch"), PAGE("wagyu-gulasch"))
    assert p.store == "Online: Wagyuhof" and p.price_eur == 13.2 and p.size_g == 300.0 and p.unit_price_eur == 44.0
    assert p.nutrition_100g == {"kcal": 203.0, "fat": 13.1, "satfat": 3.8, "carbs": 3.6, "sugar": 1.0, "protein": 17.7, "salt": 1.0}
    assert p.extra["ingredients"].startswith("70 % Rindfleisch") and p.ean is None and p.extra["available"]


def test_beuschel_typo_and_rouladen_soldout():
    b = W.to_product(next(x for x in SHOP if x["handle"] == "wagyu-beuschel"), PAGE("wagyu-beuschel"))
    assert b.nutrition_100g["satfat"] == 3.8 and b.nutrition_100g["salt"] == 1.54
    r = W.to_product(next(x for x in SHOP if x["handle"] == "wagyu-rouladen"), PAGE("wagyu-rouladen"))
    assert r.price_eur == 14.9 and not r.extra["available"] and r.nutrition_100g["kcal"] == 149.0


def test_product_lookup():
    assert W.product("https://wagyuhof.com/products/wagyu-gulasch", SHOP, PAGE("wagyu-gulasch")).source_id == "10384239296849"
    assert W.product("nope", SHOP, "") is None
