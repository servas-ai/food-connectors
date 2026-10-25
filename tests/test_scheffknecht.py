import pathlib
from food_connectors.adapters import scheffknecht as S

FX = pathlib.Path(__file__).parent / "fixtures" / "scheffknecht"


def page(name):
    return (FX / f"{name}.html").read_text()


def test_sitemap_filter():
    slugs = S.product_slugs((FX / "store-products-sitemap.xml").read_text())
    assert len(slugs) == 9 and "indisches-hühner-curry" in slugs and "süßkartoffel-kichererbsen-chili" in slugs
    assert [s for s in slugs if not S.is_meal(s)] == ["sugo-bolognese"]


def test_parse_chili_and_curry():
    p = S.product("chili-con-carne", page("chili-con-carne"))
    assert p.store == "Online: Ariane Scheffknecht" and p.price_eur == 13.5 and p.size_g == 480.0 and p.unit_price_eur == 28.12
    assert p.extra["ingredients"].startswith("Hackfleisch (Rind und Schwein), Tomaten") and p.extra["portions"] == 2
    assert p.extra["in_stock"] and "8944fc_68eeabbf" in p.image_url and p.ean is None and p.nutrition_100g == {}
    c = S.product("https://www.ariane-scheffknecht.at/product-page/indisches-h%C3%BChner-curry", page("indisches-huehner-curry"))
    assert c.name == "Indisches Hühner-Curry" and c.price_eur == 14.0 and c.size_g == 470.0 and c.source_id == "indisches-hühner-curry"


def test_no_description_and_excluded():
    g = S.product("gerstensuppe-vegan", page("gerstensuppe-vegan"))
    assert g.name == "Gerstensuppe mit Käferbohnen" and g.price_eur == 13.5 and g.size_g is None and g.extra["ingredients"] is None
    assert S.product("sugo-bolognese", page("sugo-bolognese")) is None
