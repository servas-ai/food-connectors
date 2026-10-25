import pathlib
from food_connectors.adapters import flottelotte as F

D = pathlib.Path(__file__).parent / "fixtures" / "flottelotte"
rd = lambda n: (D / n).read_text(encoding="utf-8", errors="ignore")


def test_category_slugs():
    s = F.category_slugs(rd("suppen.html"))
    assert "Kartoffel-Lauch-Suppe" in s and "Tomaten-Suppe" in s and len(s) == 7
    assert "Sugos" not in s and "Probierset-Suppen" not in s


def test_parse_linsen_gulasch():
    p = F.parse("Linsen-Gulasch", rd("linsen-gulasch.html"))
    assert p.name == "Linsen Gulasch" and p.source_id == "GK0021" and p.price_eur == 6.5 and p.size_g == 380.0
    assert p.unit_price_eur == 17.11 and p.extra["kind"] == "Eintopf" and p.extra["in_stock"] is True
    assert p.nutrition_100g == {"kcal": 74.0, "fat": 1.9, "satfat": 0.2, "carbs": 9.6, "sugar": 2.5, "protein": 2.7, "salt": 0.8}
    assert p.extra["ingredients"].startswith("Wasser, Kartoffel") and p.image_url.endswith("linsen-gulasch.jpg") and p.ean is None


def test_soup_without_photo_and_excluded():
    p = F.parse("Schwarzwurzel-Suppe", rd("schwarzwurzel-suppe.html"))
    assert p.extra["kind"] == "Suppe" and p.extra["size_unit"] == "ml" and p.unit == "l" and p.image_url is None
    assert F.product("Sugos") is None and F.slug_of("https://flottelottezwettl.at/Tarka-Dhal?x=1") == "Tarka-Dhal"
