import json, pathlib
from food_connectors.adapters import schmankerl as S

SHOP = json.loads((pathlib.Path(__file__).parent / "fixtures" / "schmankerl" / "products.json").read_text(encoding="utf-8"))["products"]
by = lambda h: next(x for x in SHOP if x["handle"] == h)


def test_filter_meals_excludes_sides_mixes_inserts():
    assert sorted(p["handle"] for p in SHOP if S.is_meal(p)) == [
        "fleischstrudel", "gulaschsuppe", "kaspressknoedel", "speckknoedel", "spinatspeckknoedel"]


def test_parse_speckknoedel():
    p = S.to_product(by("speckknoedel"))
    assert p.store == "Online: Schmankerl Österreich" and p.price_eur == 10.9 and p.size_g == 300.0 and p.unit_price_eur == 36.33
    assert p.extra["pieces"] == 4 and p.extra["ingredients"].startswith("Weißbrot, geräucherter Speck")
    assert p.extra["storage"].startswith("Gekühlt bei 4–10°C") and p.nutrition_100g == {} and p.ean is None
    assert p.image_url.split("?")[0].endswith("IMG-6807.heic")  # image 0 is the Spinat-Speck packshot


def test_gulaschsuppe_brand_and_strudel_without_weight():
    g = S.to_product(by("gulaschsuppe"))
    assert g.brand == "Felix" and g.size_g == 400.0 and g.extra["ingredients"].endswith("Kräuterextrakte")
    f = S.to_product(by("fleischstrudel"))
    assert f.size_g is None and f.unit_price_eur is None and f.extra["pieces"] == 1 and f.price_eur == 13.9


def test_product_lookup():
    assert S.product("https://schmankerl-oesterreich.at/products/kaspressknoedel", SHOP).size_g == 400.0
    assert S.product("leberknoedel", SHOP) is None and S.product("nope", SHOP) is None
