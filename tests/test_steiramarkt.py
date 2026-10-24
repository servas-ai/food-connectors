import json, pathlib
from food_connectors.adapters import steiramarkt as S

F = pathlib.Path(__file__).parent / "fixtures"
SHOP = json.loads((F / "steiramarkt_store_products.json").read_text())


def test_filter_meals():
    names = [S.to_product(p).name for p in SHOP if S.is_meal(p)]
    assert len(names) == 22 and any("Rindsgulasch" in n for n in names) and any("Kasnudeln" in n for n in names)
    bad = ("PUR", "Gulaschsaft", "Sugo", "Strudel", "Knödel", "Ge(H)würz")
    assert not any(b.lower() in n.lower() for n in names for b in bad)


def test_parse_jar_and_nutrition():
    g = S.product("4802", SHOP)
    assert g.price_eur == 9.9 and g.size_g == 400.0 and g.ean is None and g.extra["line"] == "Essen im Glas"
    k = S.product("1984", SHOP)
    assert k.nutrition_100g["kcal"] == 88.0 and k.nutrition_100g["protein"] == 3.5 and k.nutrition_100g["salt"] == 1.4
    assert k.extra["ingredients"].startswith("Käferbohnen gequollen")


def test_nudeln_and_lookup():
    n = S.product("kaerntner-kasnudeln-6-stueck-600-g", SHOP)
    assert n.size_g == 600.0 and n.extra["line"] == "Kärntner Nudeln" and n.nutrition_100g == {}
    assert S.product("5113", SHOP).extra["ingredients"].startswith("40 % Bröseltopfen")
    assert S.product("nope", SHOP) is None
