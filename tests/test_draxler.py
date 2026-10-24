import json, pathlib
from food_connectors.adapters import draxler as D

F = pathlib.Path(__file__).parent / "fixtures"
SHOP = json.loads((F / "draxler_store_products.json").read_text())
REH = (F / "draxler_rehragout.html").read_text()


def test_filter_meals():
    names = sorted(D.to_product(p, REH if p["id"] == 6561 else None).name for p in SHOP if D.is_meal(p))
    assert len(names) == 9 and "Rehragout" in names and "Klare Suppe vom Maishendl" not in names
    assert not any("Genusspaket" in n or "Gutschein" in n for n in names)


def test_parse_chili_vegan():
    p = D.to_product(next(x for x in SHOP if x["id"] == 6237))
    assert p.price_eur == 6.9 and p.size_g == 360.0 and p.extra["sku"] == "968"
    assert p.extra["vegan"] and p.extra["vegetarian"] and p.ean is None and p.nutrition_100g == {}
    assert p.extra["description_source"] == "store_api"


def test_broken_api_description_falls_back_to_page():
    p = D.product("rehragout", SHOP, page_html=REH)
    assert p.extra["description_source"] == "product_page" and p.size_g == 360.0 and p.price_eur == 10.0
    assert p.extra["ingredients"].startswith("45% Rehfleisch")
    assert D.product("nope", SHOP) is None
