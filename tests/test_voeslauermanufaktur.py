import pathlib
from food_connectors.adapters import voeslauermanufaktur as V

F = pathlib.Path(__file__).parent / "fixtures"
SHOP = (V.parse_page((F / "voeslauermanufaktur_hauptgerichte.html").read_text(), "Hauptgericht")
        + V.parse_page((F / "voeslauermanufaktur_suppen.html").read_text(), "Suppe"))


def test_filter_meals():
    names = [sp["name"] for sp in SHOP if V.is_meal(sp)]
    assert len(SHOP) == 14 and len(names) == 13
    assert "Echtes Rindssupperl" not in names and "Echtes Rindssupperl mit Fleischeinlage" in names
    assert "Rindsgulasch" in names and "Selleriecremesuppe" in names


def test_parse_jar():
    g = V.product("maad91ec5ba600c5c", SHOP)
    assert g.name == "Rindsgulasch" and g.price_eur == 10.9 and g.size_g == 345.0 and g.unit_price_eur == 3.16
    assert g.ean is None and g.nutrition_100g == {} and g.extra["ingredients"].startswith("Rindfleisch, Zwiebel")
    assert g.extra["line"] == "Hauptgericht" and g.extra["in_stock"] and g.image_url.startswith("https://image.jimcdn.com/")


def test_photo_gate_vegan_stock():
    assert V.product("mbd085715cb6d6dd5", SHOP).image_url is None  # reuses the plain Erdäpfelcremesuppe photo
    k = V.product("Karfiolcremesuppe", SHOP)
    assert k.extra["vegan"] and k.extra["line"] == "Suppe" and k.size_g == 350.0
    assert V.product("m606312a9dc547fe1", SHOP).extra["in_stock"] is False  # Polpetti sold out
    assert V.product("nope", SHOP) is None
