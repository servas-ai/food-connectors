import json, pathlib
from food_connectors.adapters import bernos as B

SHOP = json.loads((pathlib.Path(__file__).parent / "fixtures" / "bernos_store_products.json").read_text())


def test_filter_meals():
    assert [B.to_product(p).name for p in SHOP if B.is_meal(p)] == ["Rehragout", "Hirschgulasch", "Gulaschsuppe vom Wild", "Gamseintopf"]


def test_parse_rehragout():
    p = B.product("rehragout", SHOP)
    assert p.store == "Online: Bernos Tauernwild" and p.price_eur == 9.5 and p.size_g == 290.0 and p.unit_price_eur == 32.76
    assert p.extra["ingredients"].startswith("Rehfleisch, Wasser, Zwiebel") and p.extra["meat_share"] == "Rehfleischanteil: 40%"
    assert p.image_url.endswith("rehragout_small.png") and p.ean is None and p.nutrition_100g == {}


def test_excluded_lookup():
    assert B.product("wildsugo", SHOP) is None and B.product("henkele", SHOP) is None and B.product("681", SHOP) is None and B.product("nope", SHOP) is None
