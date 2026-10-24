import json, pathlib
from food_connectors.adapters import sperchenedergut as S

SHOP = json.loads((pathlib.Path(__file__).parent / "fixtures" / "sperchenedergut_store_products.json").read_text())


def test_filter_meals():
    names = sorted(S.to_product(p).name for p in SHOP if S.is_meal(p))
    assert names == ["Beuschel vom Bio-Angusrind (handgeschnitten)", "Chili con Carne vom Angusrind", "Gulaschsuppe vom Bio-Angusrind"]


def test_parse_gulasch():
    p = S.to_product(next(x for x in SHOP if x["id"] == 1338))
    assert p.store == "Online: Sperchenedergut" and p.price_eur == 9.5
    assert p.extra["volume_ml"] == 330.0 and p.extra["portion_g"] == 300.0 and p.extra["bio_claim"]
    assert p.image_url.endswith("shop-produkte-gulasch-01.jpg") and p.ean is None and p.nutrition_100g == {}


def test_product_lookup():
    assert S.product("chiliconcarne-vom-angusrind", SHOP).source_id == "1333"
    assert S.product("1336", SHOP).name.startswith("Beuschel")
    assert S.product("nope", SHOP) is None
