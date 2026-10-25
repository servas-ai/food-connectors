import json, pathlib
from food_connectors.adapters import regionalles as R

ITEMS = json.loads((pathlib.Path(__file__).parent / "fixtures" / "regionalles" / "products_p1.json").read_text())["products"]


def test_filter_meals():
    ps = R.all_products(ITEMS)
    assert len(ps) == 6 and {p.extra["handle"] for p in ps} == R.MEALS
    assert all(p.ean is None and p.nutrition_100g == {} for p in ps)


def test_parse_hold_jar():
    g = R.product("gulasch-im-glas", ITEMS)
    assert g.name == "Holdi's Gulasch im Glas" and g.price_eur == 8.4 and g.size_g == 427.0 and g.unit_price_eur == 19.67
    assert g.brand == "Gastwirtschaft Hold" and g.image_url.endswith("Gulasch.jpg")


def test_vision_gate_and_excluded():
    s = R.product("https://www.regionalles.com/products/holdis-chili-sin-carne-im-glas", ITEMS)
    assert s.image_url is None and s.extra["veg"]
    f = R.product("jobi-fischsuppe", ITEMS)
    assert f.size_g == 430.0 and f.extra["in_stock"]
    assert R.product("jobi-roller", ITEMS) is None
