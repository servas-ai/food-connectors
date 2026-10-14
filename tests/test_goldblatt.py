import json, pathlib
from food_connectors.adapters import goldblatt as G

FX = pathlib.Path(__file__).parent / "fixtures"
H = (FX / "goldblatt_chili-con-tempeh.html").read_text()
SP = json.loads((FX / "goldblatt_chili-con-tempeh.json").read_text())["product"]
SHOP = json.loads((FX / "goldblatt_products.json").read_text())["products"]


def test_parse_nutrition_and_product():
    per100, pack, size = G.parse_nutrition(H)
    assert size == 500.0
    assert per100["kcal"] == 97.0 and per100["protein"] == 7.0 and per100["fat"] == 1.4
    assert per100["satfat"] == 0.3 and per100["carbs"] == 12.0 and per100["sugar"] == 2.1
    assert per100["fiber"] == 4.9 and per100["salt"] == 0.72
    assert pack["kcal"] == 485.0 and pack["protein"] == 35.0
    p = G.to_product(SP, H)
    assert p.source == "goldblatt" and p.store == "Online: Goldblatt" and p.brand == "Goldblatt"
    assert p.name == "Chili con Tempeh" and p.price_eur == 11.99 and p.size_g == 500.0
    assert p.unit_price_eur == round(11.99 / 500 * 1000, 2) and p.unit == "kg"
    assert p.nutrition_100g == per100 and p.ean is None
    assert p.image_url and ("cdn.shopify.com" in p.image_url or "goldblatt.at/cdn" in p.image_url)
    assert p.extra["portions"] == 2 and p.extra["bio"] is True
    assert p.extra["ingredients"] and "Tempeh" in p.extra["ingredients"]
    assert G.is_ready_meal(p)
    shop_chili = next(x for x in SHOP if x["handle"] == "chili-con-tempeh")
    p2 = G.to_product(shop_chili, H)
    assert p2.extra["available"] is True


def test_is_meal_filters():
    chili = next(p for p in SHOP if p["handle"] == "chili-con-tempeh")
    assert G.is_meal(chili)
    bundle = next(p for p in SHOP if p["handle"] == "kennenlernen-bio-gerichte")
    assert not G.is_meal(bundle)
    monats = next(p for p in SHOP if p["handle"] == "4-wochen-bundle")
    assert not G.is_meal(monats)
    wurst = next(p for p in SHOP if p["handle"] == "edelpilz-rauchwurst")
    assert not G.is_meal(wurst)
    topping = next(p for p in SHOP if p["handle"] == "bio-avocado-affair-topping")
    assert not G.is_meal(topping)


def test_missing_html_keeps_nulls():
    p = G.to_product(SP, "")
    assert p.size_g is None and p.nutrition_100g == {} and not G.is_ready_meal(p)


def test_all_eight_meal_handles_present():
    meals = [p for p in SHOP if G.is_meal(p)]
    handles = {p["handle"] for p in meals}
    expected = {
        "chili-con-tempeh", "bio-kichererbsen-curry", "bio-bolognese", "bio-edelpilz-gulasch",
        "bio-alpine-bowl", "bio-oriental-bowl", "bio-letscho-bowl", "bio-erdapfel-gulasch",
    }
    assert handles == expected
