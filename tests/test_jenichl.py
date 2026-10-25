import json, pathlib
from food_connectors.adapters import jenichl as J, ADAPTERS

FX = pathlib.Path(__file__).parent / "fixtures"


def _all():
    return [J.parse_product(x) for x in J.products_from_catalog(json.loads((FX / "jenichl_catalog.json").read_text()))]


def test_jar_meal_fields_and_photo_pick():
    g = next(p for p in _all() if p.source_id == "241886285")
    assert g.source == "jenichl" and g.name == "Gulasch im Glas" and g.price_eur == 5.5 and g.size_g == 390.0
    assert g.ean is None and g.nutrition_100g == {} and g.extra["frozen"] is False
    assert g.extra["ingredients"].startswith("Wasser, 35% Schweinefleisch") and "SULFITE" in g.extra["allergens_marked"]
    assert g.image_url and g.image_url.endswith("1693878467.jpg")  # 2nd picture: 'Gulasch essfertig' jar, not Gulaschsaft
    assert g.source_url.startswith("https://www.genussbauernhof-jenichl.at/shop#!/")
    pa = next(p for p in _all() if p.source_id == "242392425")
    assert pa.size_g == 640.0 and pa.extra["ingredients"].startswith("53% Tomatensauce")


def test_knoedel_frozen_and_shared_photo():
    ps = {p.source_id: p for p in _all()}
    s = ps["242413896"]
    assert s.extra["frozen"] and s.extra["pieces"] == 10 and s.price_eur == 10.0 and s.image_url
    assert not s.extra["ingredients"].endswith("siedendes Wasser geben!")
    h = ps["242801295"]
    assert h.image_url is None and h.extra["shared_image_url"]


def test_meal_filter():
    meals = [p for p in _all() if J.is_meal_name(p.name)]
    assert len(meals) == 11
    for n in ["Gulaschsaft", "Pasta Asciutta Sugo", "Chili Dip", "Semmelknödel (4 Stk.)", "Innviertler Surspeck",
              "Leberkäse Pikant", "Frankfurter;      1 Paar", "Fleischaufstrich", "Sulz"]:
        assert not J.is_meal_name(n), n


def test_registered():
    assert ADAPTERS["jenichl"].status == "live"
