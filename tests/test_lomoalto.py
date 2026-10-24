import json, pathlib
from food_connectors.adapters import lomoalto as L

SHOP = json.loads((pathlib.Path(__file__).parent / "fixtures" / "lomoalto_products.json").read_text())["products"]


def test_filter_meals():
    assert sorted(L._sku(p) for p in SHOP if L.is_meal(p)) == ["FERTIGP1", "FERTIGP2", "FERTIGP4"]


def test_gulasch_label():
    g = L.product("FERTIGP1", SHOP)
    assert g.name == "BIO Rindergulasch im Glas 400g" and g.price_eur == 12.4 and g.size_g == 400.0 and g.unit_price_eur == 3.1
    assert g.ean == "9120082120050" and g.nutrition_100g["protein"] == 13.85 and g.nutrition_100g["kcal"] == 147.6
    assert g.extra["ingredients"].startswith("Rindfleisch*") and "etikett" not in g.image_url


def test_lookup_and_label_guard():
    c = L.product("chili-con-carne-im-glas-400g", SHOP)
    assert c.ean == "9120082120067" and c.nutrition_100g["salt"] == 0.59
    sp = dict(next(p for p in SHOP if L._sku(p) == "FERTIGP2")); sp["images"] = sp["images"][:1]
    assert L.to_product(sp).ean is None and L.to_product(sp).nutrition_100g == {}
    assert L.product("nope", SHOP) is None
