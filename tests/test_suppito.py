import json, pathlib
from food_connectors.adapters import suppito as S

F = pathlib.Path(__file__).parent / "fixtures"
SHOP = json.loads((F / "suppito_store_products.json").read_text())


def test_filter_meals():
    names = [S.to_product(p).name for p in SHOP if S.is_meal(p)]
    assert len(names) == 18 and any("Minestrone" in n for n in names) and any("Rindsgulasch" in n for n in names)
    bad = ("Sugo", "Bolognese", "Brodo", "Dressing", "Porridge")
    assert not any(b.lower() in n.lower() for n in names for b in bad)


def test_parse_jar():
    g = S.product("269", SHOP)
    assert g.price_eur == 11.1 and g.size_g == 510.0 and g.unit_price_eur == 2.18 and g.ean is None
    assert g.extra["vegan"] and g.extra["line"] == "Eintopf" and g.nutrition_100g == {}
    assert g.extra["ingredients"].startswith("42% Erdäpfel") and g.image_url.endswith("Erdaepfelgulasch_Raeuchertofu-scaled.webp")


def test_photo_gate_and_lookup():
    assert S.product("51447", SHOP).image_url is None  # reuses the Gigantes photo
    assert S.product("4804", SHOP).extra["vegetarian"] is False
    assert S.product("gemuesesuppe-italienisch", SHOP).extra["line"] == "Suppe"
    assert S.product("nope", SHOP) is None
