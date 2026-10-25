import json, pathlib
from food_connectors.adapters import leitgeb as L

FX = pathlib.Path(__file__).parent / "fixtures" / "leitgeb"
SHOP = json.loads((FX / "store_products.json").read_text())


def test_filter_meals():
    assert {L._name(p) for p in SHOP if L.is_meal(p)} == {"Käspressknödel", "Kärntner Fleischnudel", "Kärntner Käsnudel"}


def test_parse_kaesnudel():
    p = L.product("3193", SHOP, (FX / "3193.html").read_text())
    assert p.store == "Online: Leitgeb's Kärntnernudel" and p.price_eur == 10.7 and p.size_g == 450.0 and p.unit_price_eur == 23.78
    assert p.nutrition_100g == {"kj": 825.0, "kcal": 196.0, "fat": 4.9, "saturated_fat": 2.2, "carbs": 29.0, "sugar": 2.1, "protein": 7.4, "salt": 1.6}
    assert p.extra["ingredients"].startswith("40 % Bröseltopfen") and p.extra["allergens"] == "Eier, Gluten, Milch" and p.ean is None


def test_fleischnudel_and_excluded():
    p = L.product("kaerntner-fleischnudel", SHOP, (FX / "3223.html").read_text())
    assert p.size_g == 900.0 and p.extra["pieces"] == 10 and p.nutrition_100g["protein"] == 17.0
    assert L.product("3213", SHOP, "") is None and L.product("3197", SHOP, "") is None and L.product("nope", SHOP, "") is None
