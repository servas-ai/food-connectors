import pathlib
from food_connectors.adapters import gerbl as G, ADAPTERS

FX = pathlib.Path(__file__).parent / "fixtures"
CAT = (FX / "gerbl_category.html").read_text()


def test_category_links_incl_slug():
    ts = G.parse_category(CAT)
    assert len(ts) == 22
    ids = {t["id"] for t in ts}
    assert "796880" in ids and "rindsgulasch" in ids  # GIG01 is linked by vanity slug only
    assert next(t for t in ts if t["id"] == "rindsgulasch")["url"] == "https://shop.gerbl.at/rindsgulasch"


def test_product_vegetarian_curry():
    p = G.parse_product((FX / "gerbl_kichererbsencurry_796889.html").read_text(), "https://shop.gerbl.at/ecommerce/product?product_id=796889&category_id=150129")
    assert p.source == "gerbl" and p.store == "Online: Gerbl im Glas" and p.name == "Kichererbsencurry"
    assert p.price_eur == 9.0 and p.size_g is None and p.ean is None and p.nutrition_100g == {}
    assert p.extra["article_code"] == "GIG12" and p.extra["volume_ml"] == 450.0 and p.extra["vegetarian"] is True
    assert p.image_url.startswith("https://shop.gerbl.at/gallery-file/") and p.image_url.endswith("/picture-orig.jpg")


def test_product_slug_and_bundle_filter():
    r = G.parse_product((FX / "gerbl_rindsgulasch.html").read_text(), "https://shop.gerbl.at/rindsgulasch")
    assert r.name == "Rindsgulasch" and r.extra["article_code"] == "GIG01" and r.source_id == "796908"
    assert r.extra["allergens"] == "A" and "12 Wochen" in r.extra["shelf_life"] and G.is_meal_name(r.name)
    k = G.parse_product((FX / "gerbl_geschenkskorb_796904.html").read_text(), "https://shop.gerbl.at/ecommerce/product?product_id=796904&category_id=150129")
    assert not G.is_meal_name(k.name) and not G.is_meal_name("Die Goldene -Grobe Leberstreichwurst")


def test_registered():
    assert ADAPTERS["gerbl"].status == "live"
