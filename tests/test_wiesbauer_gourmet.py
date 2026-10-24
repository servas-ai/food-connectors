import json, pathlib
from food_connectors.adapters import wiesbauer_gourmet as W

F = pathlib.Path(__file__).parent / "fixtures"
SHOP = json.loads((F / "wiesbauer_gourmet_store_products.json").read_text())


def test_filter_meals():
    names = [W.to_product(p).name for p in SHOP if W.is_meal(p)]
    assert len(names) == 20 and any("Rindergulasch" in n for n in names)
    bad = ("Sauce", "Bratensaft", "Geflügelsaft", "Knödel", "Rotkraut", "Package", "Paket", "Tatar", "Würstel", "paniert", "Pulled Pork", "Roastbeef")
    assert not any(b.lower() in n.lower() for n in names for b in bad)


def test_parse_gulasch_nutrition():
    p = W.product("111005", SHOP)
    assert p.price_eur == 10.9 and p.size_g == 280.0 and p.extra["sku"] == "92103" and p.ean is None
    assert p.nutrition_100g["kcal"] == 179.0 and p.nutrition_100g["protein"] == 13.0 and p.nutrition_100g["salt"] == 1.9
    assert p.extra["ingredients"].startswith("Rindfleisch (57%)")


def test_inconsistent_energy_is_dropped_and_size_from_description():
    t = W.product("5146", SHOP)
    assert t.nutrition_100g == {} and t.extra["nut_flag"] == "shop_kj_kcal_inconsistent"
    assert W.product("118741", SHOP).size_g == 900.0
    assert W.product("nope", SHOP) is None
