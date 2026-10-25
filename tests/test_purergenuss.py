import json, pathlib
from food_connectors.adapters import purergenuss as P

FX = pathlib.Path(__file__).parent / "fixtures" / "purergenuss"
SHOP = json.loads((FX / "store_products.json").read_text())


def test_filter_meals():
    assert {P._name(p) for p in SHOP if P.is_meal(p)} == {"Wildbeuschel", "Chilli Con Wild", "Reh Ragout",
        "Wildsuppe mit Fleisch und Gemüse", "Wildschweinbraten", "Hirschbraten", "Hirschragout"}


def test_parse_hirschbraten():
    p = P.product("hirschbraten", SHOP)
    assert p.store == "Online: Purer Genuss (Schüsseltrieb)" and p.brand == "Schüsseltrieb Manufaktur" and p.price_eur == 12.99
    assert p.size_g is None and p.nutrition_100g == {} and p.ean is None and p.extra["vegetarian"] is False
    assert p.image_url.endswith("PhotoRoom_20210425_140122.jpg") and p.source_url == "https://www.purer-genuss.at/product/hirschbraten/"


def test_prices_and_excluded():
    ps = P.all_products(SHOP)
    assert len(ps) == 7 and min(p.price_eur for p in ps) == 6.99 and max(p.price_eur for p in ps) == 14.99
    assert P.product("186", SHOP) is None and P.product("wildsugo", SHOP) is None and P.product("nope", SHOP) is None
