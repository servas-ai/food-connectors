import json, pathlib
from food_connectors.adapters import kernbeisser as K

FX = pathlib.Path(__file__).parent / "fixtures"
SHOP = json.loads((FX / "kernbeisser_store_products.json").read_text())
PAGE = (FX / "kernbeisser_maghreb-hirse_jsonld.html").read_text()


def test_parse_maghreb():
    sp = next(p for p in SHOP if p["slug"] == "maghreb-hirse-mit-artischocken")
    p = K.to_product(sp, PAGE)
    assert p.source == "kernbeisser" and p.store == "Online: Kernbeißer" and p.brand == "Kernbeißer"
    assert p.price_eur == 9.0 and p.size_g == 450.0 and p.unit == "kg"
    n = p.nutrition_100g
    assert n["kcal"] == 116.0 and n["fat"] == 3.9 and n["satfat"] == 0.5 and n["carbs"] == 15.4
    assert n["sugar"] == 4.3 and n["fiber"] == 4.2 and n["protein"] == 4.1 and n["salt"] == 0.8
    assert p.extra["kcal_jar"] == 522.0 and p.extra["vegan"] and p.extra["glutenfrei"]
    assert p.extra["ingredients"].startswith("Artischocken (22%)")
    assert p.ean == "9180025580068"
    assert p.image_url.startswith("https://kernbeisser.at/wp-content/uploads/")
    assert K.is_ready_meal(p)


def test_filters_bundle():
    assert not K.is_meal(next(p for p in SHOP if p["slug"].startswith("kernbeisser-probierpaket") or "Probierpaket" in p["name"]))
    assert sum(K.is_meal(p) for p in SHOP) == 6


def test_all_meals_parse():
    for sp in SHOP:
        if K.is_meal(sp):
            p = K.to_product(sp)
            assert K.is_ready_meal(p), sp["slug"]


def test_bad_gtin_rejected():
    assert K.parse_gtin('"gtin":"9180025580069"') is None
    assert K.parse_gtin("") is None
