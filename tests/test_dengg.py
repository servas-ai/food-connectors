import pathlib
from food_connectors.adapters import dengg as D

F = pathlib.Path(__file__).parent / "fixtures" / "dengg"
rd = lambda n: (F / n).read_text(encoding="utf-8", errors="ignore")


def test_category_filter():
    s = D.meal_slugs([rd("knoedel.html")])
    assert "kaspressknoedel-4-stk--62238307" in s and "tiroler-speckknoedel-4-stk--62239296" in s
    assert not any(x.startswith("semmelknoedel") for x in s) and len(s) == 6


def test_parse_kaspressknoedel_with_datasheet():
    p = D.parse("kaspressknoedel-4-stk--62238307", rd("kaspressknoedel.html"), rd("kaspressknoedel.txt"))
    assert p.name == "Kaspressknödel 4 Stk." and p.price_eur == 7.2 and p.size_g == 400.0 and p.unit_price_eur == 18.0 and "brutto" in p.extra["price_basis"]
    assert p.nutrition_100g["energy_kcal"] == 234.0 and p.nutrition_100g["proteins"] == 9.1 and p.nutrition_100g["salt"] == 1.6
    assert p.extra["ld_offer_price"] == 7.2 and p.extra["veg"] and p.ean is None
    assert "KÄSE (13%)" in p.extra["ingredients"] and p.image_url.endswith(".jpg")


def test_missing_datasheet_and_excluded():
    k = D.parse("kuerbisknoedel-4-stk--62241432", rd("kuerbisknoedel.html"), None)
    assert k.size_g == 400.0 and k.nutrition_100g == {} and k.price_eur == 6.8 and "berechnet" in k.extra["price_basis"]
    assert D.parse("marillenkrapfen-15-stk--62242205", "", None) is None
    assert D.slug_of("https://www.dengg.info/kaspressknoedel-4-stk--62238307-de.html") == "kaspressknoedel-4-stk--62238307"
    assert D.slug_of("62238307") == "kaspressknoedel-4-stk--62238307"
