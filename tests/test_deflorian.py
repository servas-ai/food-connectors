import json, pathlib
from food_connectors.adapters import deflorian as D

FX = pathlib.Path(__file__).parent / "fixtures"
SHOP = json.loads((FX / "deflorian_products.json").read_text())["products"]
PAGE = (FX / "deflorian_kaspressknodel.html").read_text()


def test_filter_meals():
    m = {p["handle"] for p in SHOP if D.is_meal(p)}
    assert len(m) == 27 and "rindsgulasch" in m and "zillertaler-mini" in m and "marillenknodel-mit-kern" in m
    assert not m & {"fleischsugo", "semmelknodel", "leberknodel", "milzschnitten", "sauerkraut", "kiachl-gebacken",
                    "probierpaket-vegetarische-klassiker", "deflorian-gutschein", "schokoladen-gugelhupf"}


def test_kaspressknodel_with_ingredients():
    p = D.product("kaspressknodel-vorgebacken", SHOP, PAGE)
    assert p.name == "Kaspressknödel vorgebacken" and p.price_eur == 8.2 and p.size_g == 400.0 and p.unit_price_eur == 2.05
    assert p.extra["pack"] == "4 Stück" and p.extra["ingredients"].startswith("Knödelbrot (WEIZENMEHL")
    assert p.nutrition_100g == {} and p.ean is None and p.image_url.startswith("https://cdn.shopify.com/")


def test_lookup_kind_and_search_offline():
    g = D.to_product(next(p for p in SHOP if p["handle"] == "gulaschsuppe"))
    assert g.extra["kind"] == "Suppe" and g.price_eur == 3.9 and g.size_g == 500.0
    assert D.product("15579425767754", SHOP, "<html></html>").extra["ingredients"] is None
    assert D.kind(next(p for p in SHOP if p["handle"] == "erdbeerknodel")) == "süße Hauptspeise"
