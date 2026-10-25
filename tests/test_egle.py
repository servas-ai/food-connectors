import pathlib
from food_connectors.adapters import egle as E

D = pathlib.Path(__file__).parent / "fixtures" / "egle"
rd = lambda n: (D / n).read_text(encoding="utf-8", errors="ignore")


def test_category_slugs_excludes_sides():
    s = E.category_slugs(rd("wild.html"))
    assert s == ["Hirsch-Gulasch-400-g", "Reh-Ragout-400-g", "Wild-Rahm-Suppe-400-g"]
    assert "BIO-Wild-Preiselbeeren-240-g" not in s


def test_parse_hirsch_gulasch():
    p = E.parse("Hirsch-Gulasch-400-g", rd("hirsch-gulasch.html"))
    assert p.name == "Hirsch-Gulasch, 400 g" and p.source_id == "159" and p.price_eur == 6.99 and p.size_g == 400.0
    assert p.unit_price_eur == 17.48 and p.unit == "kg" and p.extra["in_stock"] is True and p.extra["packaging"] == "Dose"
    assert p.nutrition_100g == {"kcal": 91.0, "fat": 3.0, "satfat": 0.9, "carbs": 5.0, "sugar": 2.5, "protein": 11.0, "salt": 0.8}
    assert p.extra["ingredients"].startswith("Hirschfleisch 51%") and p.image_url.split("?")[0].endswith("_F01.webp") and p.ean is None


def test_soup_out_of_stock_and_excluded():
    p = E.parse("BIO-Kaesenockerl-Suppe-400-ml", rd("kaesenockerl-suppe.html"))
    assert p.extra["kind"] == "Suppe" and p.extra["size_unit"] == "ml" and p.unit == "l" and p.extra["bio"] is True
    assert p.extra["in_stock"] is False and p.origin == "Deutschland" and p.nutrition_100g["kcal"] == 46.0
    assert E.product("Nordische-Lachssuppe-2-x-410-ml") is None and E.product("BIO-Sauce-Bolognese-400-g") is None
    assert E.slug_of("https://www.egleshop.at/Reh-Ragout-400-g?x=1") == "Reh-Ragout-400-g"
