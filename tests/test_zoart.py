import json, pathlib
from food_connectors.adapters import zoart as Z

FX = pathlib.Path(__file__).parent / "fixtures" / "zoart"
SHOP = json.loads((FX / "store_products.json").read_text())
VAR = json.loads((FX / "variations.json").read_text())
vg = lambda i: VAR[str(i)]


def test_filter_and_variants():
    ps = Z.all_products(SHOP, vg)
    assert len(ps) == 19 and min(p.price_eur for p in ps) == 8.3 and max(p.price_eur for p in ps) == 25.5
    names = {p.name for p in ps}
    assert "Schweinebauch asiatisch 1300g" in names and "Karreebraten mit Schwarte 700g" in names
    assert not any("Zunge" in n or "Bratensaft" in n for n in names)


def test_parse_simple_products():
    r = Z.product("schweinsrouladen-mit-speck", SHOP, vg)
    assert r.price_eur == 10.0 and r.size_g == 550.0 and r.unit_price_eur == 18.18 and r.ean is None and r.nutrition_100g == {}
    assert r.image_url.endswith("Rouladen-scaled.jpg") and r.store == "Online: Sous Vide Fertiggerichte (zoart)"
    g = Z.product("291", SHOP, vg)
    assert g.size_g == 700.0 and g.extra["size_unit"] == "ml" and g.unit == "l" and g.extra["meat_g"] == 350.0 and g.extra["packaging"] == "Glas"


def test_variation_and_excluded():
    v = Z.product("275", SHOP, vg)
    assert v.name == "Schweinebauch asiatisch 1300g" and v.price_eur == 25.5 and v.size_g == 1300.0 and v.extra["wc_id"] == 216
    assert Z.product("zunge", SHOP, vg) is None and Z.product("367", SHOP, vg) is None and Z.product("nope", SHOP, vg) is None
