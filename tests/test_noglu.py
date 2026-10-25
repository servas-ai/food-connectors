import json, pathlib
from food_connectors.adapters import noglu as N

SHOP = json.loads((pathlib.Path(__file__).parent / "fixtures" / "noglu" / "store_products.json").read_text())


def test_filter_meals():
    ps = N.all_products(SHOP)
    assert sorted(p.source_id for p in ps) == ["KN-KASNOCKEN", "KN-KASPRESS", "KN-SPECK", "KN-SPINAT"]
    assert all(p.price_eur == 9.0 and p.size_g == 500.0 and p.unit_price_eur == 18.0 and p.ean is None for p in ps)
    assert not any("Semmel" in p.name or "box" in p.name.lower() for p in ps)


def test_parse_speckknoedel_nutrition():
    p = N.product("glutenfreie-speckknoedel", SHOP)
    assert p.name == "Glutenfreie Speckknödel, 4 Stück (500 g)" and p.extra["pieces"] == 4 and p.extra["piece_g"] == 125.0
    assert p.nutrition_100g == {"kcal": 175.0, "fat": 5.4, "satfat": 1.8, "carbs": 23.9, "sugar": 1.1, "fiber": 1.5,
                                "protein": 6.6, "salt": 2.46}
    assert p.extra["kj_100"] == 728.0 and p.image_url.endswith("speckknoedel.jpg") and p.extra["in_stock"] is True


def test_lookup_and_excluded():
    assert N.product("122", SHOP).nutrition_100g["kcal"] == 128.0
    assert N.product("KN-KASNOCKEN", SHOP).store == "Online: NoGlu (glutenfreie Knödel)"
    assert N.product("glutenfreie-semmelknoedel", SHOP) is None and N.product("185", SHOP) is None
    assert N.product("nope", SHOP) is None
