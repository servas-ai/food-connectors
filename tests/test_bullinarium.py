import pathlib
from food_connectors.adapters import bullinarium as B

FX = pathlib.Path(__file__).parent / "fixtures" / "bullinarium"
SLUGS = ["bull-beef-geschmorte-wade", "bull-beef-bbq-ribs-in-the-box", "chili-con-bull-beef", "bull-beef-gulasch-350g"]


def page(name):
    return (FX / f"{name}.html").read_text()


def test_category_filter():
    slugs = B.product_slugs(page("cat_fixfertig"))
    assert len(slugs) == 9 and [s for s in slugs if B.is_meal(s)] == SLUGS
    assert "fix-fertig-duo-vom-bull-beef" in slugs and "bull-beef-sugo-350g" in slugs


def test_parse_jars():
    g = B.product("bull-beef-gulasch-350g", page("bull-beef-gulasch-350g"))
    assert g.store == "Online: Bullinarium (Hallers Bull Beef)" and g.price_eur == 11.76 and g.size_g == 350.0
    assert g.unit_price_eur == 33.6 and g.source_id == "33020" and g.extra["in_stock"] and g.ean is None and g.nutrition_100g == {}
    assert g.extra["ingredients"].startswith("Gulaschfleisch vom Rind") and g.image_url.endswith("Gulasch_Karton.jpg")
    c = B.product("https://www.bullinarium.com/online-shop/produkt/c/fix-fertig/p/chili-con-bull-beef/", page("chili-con-bull-beef"))
    assert c.name == "Chili con Bull Beef®" and c.extra["size_label"] == "0,35 l" and c.extra["ingredients"].startswith("Rindfleisch faschiert")


def test_big_pieces_and_excluded():
    w = B.product("bull-beef-geschmorte-wade", page("bull-beef-geschmorte-wade"))
    assert w.name == "Bull Beef geschmorte Wade" and w.price_eur == 64.9 and w.size_g == 2800.0 and w.extra["persons"] == "4–6"
    assert not w.extra["in_stock"] and w.extra["on_request"]
    r = B.all_products({s: page(s) for s in SLUGS}, page("cat_fixfertig"))
    assert [p.source_id for p in r] == ["33031", "33012", "33071", "33020"]
    assert B.product("bull-beef-sugo-350g", page("bull-beef-sugo-350g")) is None
