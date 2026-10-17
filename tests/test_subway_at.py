import pathlib
from food_connectors.adapters import subway_at as S

FX = pathlib.Path(__file__).parent / "fixtures"


def test_sandwich_tiles():
    ts = S.parse_tiles((FX / "subway_at_sandwiches.html").read_text(), "Sandwiches")
    names = {t["name"] for t in ts}
    assert len(ts) == 14 and {"Tuna", "Chicken Teriyaki", "Philly Beef & Cheese", "Veggie Delite®"} <= names
    tuna = next(t for t in ts if t["name"] == "Tuna")
    assert tuna["id"] == "5261" and tuna["image_url"] == "https://www.subway.com/de-at/ns/images/menu/AST/GER/Tuna_SdT_234x140.png"
    assert tuna["url"].startswith("https://www.subway.com/de-AT/MenuNutrition/Menu/Product?ProductId=5261")
    assert tuna["description"] and not tuna["generic_tile"]


def test_series_tiles_and_product():
    ts = S.parse_tiles((FX / "subway_at_series.html").read_text(), "SubwaySeries")
    assert [t["id"] for t in ts] == ["13246", "13247", "12118", "12107", "12120", "12116"]
    p = S.to_product(ts[0])
    assert p.source == "subway-at" and p.name == "Beef Texicana" and p.category == "Unsere Kreationen"
    assert p.price_eur is None and p.image_url.endswith("Beef_Texicana_UnsKreat_234x140.png")
    assert "Cheddar" in p.extra["description"]


def test_generic_tile_has_no_dish_photo_and_norm():
    t = {"id": "7083", "name": "Wraps", "description": None, "image_url": "https://x/w.jpg", "url": "u", "category": "Salads-and-Wraps", "generic_tile": True}
    assert S.to_product(t).image_url is None
    assert S.norm("Smokey Beast") == S.norm("Smoky Beast") and S.norm("Italian B.M.T.®") == S.norm("Italian B.M.T.")
