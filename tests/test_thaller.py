import json, pathlib
from food_connectors.adapters import thaller as T

SHOP = json.loads((pathlib.Path(__file__).parent / "fixtures" / "thaller_store_products.json").read_text())


def test_filter_meals():
    assert [T.to_product(p).name for p in SHOP if T.is_meal(p)] == ["Rindsgulasch im Glas"]


def test_parse_rindsgulasch():
    p = T.product("rindsgulasch-im-glas", SHOP)
    assert p.store == "Online: Fleischhauerei Thaller" and p.price_eur == 7.5 and p.size_g == 350.0 and p.unit_price_eur == 21.43
    assert p.extra["ingredients"].startswith("45% Rindfleisch") and "WEIZENMEHL" in p.extra["ingredients"]
    assert p.extra["storage"].startswith("gekühlt 2 °C – 4 °C, 60 Tage")
    assert p.image_url.endswith("Gulasch-bea-kw-15-1.jpg") and p.ean is None and p.nutrition_100g == {}


def test_excluded_lookup():
    assert T.product("rindssuppe-im-glas", SHOP) is None and T.product("4098", SHOP) is None and T.product("nope", SHOP) is None
