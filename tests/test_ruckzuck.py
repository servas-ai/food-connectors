import json, pathlib
from food_connectors.adapters import ruckzuck as R, ADAPTERS

FX = pathlib.Path(__file__).parent / "fixtures"


def test_sitemap_product_ids():
    ts = R.parse_sitemap((FX / "ruckzuck_sitemap.xml").read_text())
    assert len(ts) == 17
    t = next(t for t in ts if t["id"] == "730940883")
    assert t["url"] == "https://www.ruckzuck-laden.at/shop/Curry-mit-Huhn-p730940883"


def test_chili_packshot_and_ingredients():
    p = R.parse_product(json.loads((FX / "ruckzuck_730952118_chili.json").read_text()))
    assert p.source == "ruckzuck" and p.name == "Chili con Carne" and p.price_eur == 8.4
    assert p.ean is None and p.size_g is None and p.nutrition_100g == {}
    assert p.extra["vat_percent"] == 10.0 and p.extra["allergens_marked"] == ["SELLERIE"]
    assert p.extra["ingredients"].startswith("Rind- und Schweinefleisch")
    # packshot (white jar photo) is the image, the main serving illustration only goes to extra
    assert p.image_url and p.image_url != p.extra["serving_image_url"]
    assert p.source_url == "https://www.ruckzuck-laden.at/shop/Chili-con-Carne-p730952118"


def test_vegan_volume_and_filter():
    p = R.parse_product(json.loads((FX / "ruckzuck_730894447_erdaepfelgulasch.json").read_text()))
    assert p.extra["vegan"] is True and p.extra["volume_ml"] == 315.0
    assert p.extra["ingredients"].startswith("Soße: Wasser")
    assert R.is_meal_name(p.name) and R.is_meal_name("Gulasch vom Rind")
    for n in ["kräftige Rindsuppe", "Sugo Bolognese Rind und Schwein", "Pastasoße VEGAN", "Gulaschsaft",
              "Apfel-Rotkraut", "Hallo Baby Box", "Kekse mit Sinn - Gute Laune Bio"]:
        assert not R.is_meal_name(n), n


def test_registered():
    assert ADAPTERS["ruckzuck"].status == "live"
