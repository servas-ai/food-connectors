import json, pathlib
from food_connectors.adapters import alfies as A

FX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "alfies_products.json").read_text())


def _p(key):
    return A.to_product(FX[key]["hit"], FX[key]["detail"], "altha")


def test_canned_chili_tab_table_kcal_first():
    p = _p("chili")
    assert p.source == "alfies" and p.store == "Alfies" and p.brand
    assert p.name == "Inzersdorfer Chilli con Carne" and p.size_g == 400.0
    n = p.nutrition_100g
    assert n["kcal"] == 89.0 and n["fat"] == 3.7 and n["satfat"] == 1.1 and n["carbs"] == 8.6
    assert n["sugar"] == 1.9 and n["protein"] == 4.2 and n["salt"] == 1.3
    assert p.price_eur and p.unit_price_eur and p.source_url.startswith("https://www.alfies.at/produkt/")
    assert p.image_url.startswith("https://static.alfies.at/") and p.ean is None
    assert p.extra["nutrition_consistent"] and A.is_ready_meal(p)


def test_pizza_label_value_split_across_br():
    n = _p("pizza").nutrition_100g
    assert n["kcal"] == 273.0 and n["protein"] == 10.0 and n["fat"] == 14.0 and n["satfat"] == 4.8
    assert n["carbs"] == 26.0 and n["sugar"] == 3.1 and n["salt"] == 1.4
    assert _p("pizza").extra["frozen"] is True


def test_missing_values_do_not_borrow_next_row():
    n = _p("wegschaider").nutrition_100g
    assert "satfat" not in n and "fiber" not in n  # "kA" in the source table
    assert n["kcal"] == 228.0 and n["protein"] == 11.5 and n["fat"] == 11.4


def test_swapped_kj_kcal_fails_plausibility():
    p = _p("fluegerl")
    assert p.nutrition_100g["kcal"] == 862.0 and p.extra["nutrition_consistent"] is False


def test_colon_format_kochsalz_and_lt():
    n, meta = A.parse_nutrition(FX["stelze"]["detail"]["attributes"]["nutrition"])
    assert n["salt"] == 2.0 and n["protein"] == 18.0 and n["carbs"] == 0.5 and "carbs" in meta["lt"]


def test_filters_and_title_cleanup():
    assert not A.is_meal_hit(FX["teig"]["hit"])
    assert A.is_meal_hit(FX["chili"]["hit"])
    assert _p("lasagne").name == "Mama Lucia Lasagne Bolognese"
    assert A.clean_title("ÜZ_Saison_ Tante Fanny Honiglebkuchenteig") == "Tante Fanny Honiglebkuchenteig"
