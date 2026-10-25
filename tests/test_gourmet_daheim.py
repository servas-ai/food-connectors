import pathlib
from food_connectors.adapters import gourmet_daheim as G

FX = pathlib.Path(__file__).parent / "fixtures"
PT = (FX / "gourmet_daheim_prices_sample.txt").read_text(encoding="utf-8")
NT = (FX / "gourmet_daheim_nutrition_sample.txt").read_text(encoding="utf-8")

def test_parse_prices():
    ps = {p["art"]: p for p in G.parse_prices(PT)}
    assert ps["2313122"]["name"] == "Alt-Wiener Suppentopf" and ps["2313122"]["size_g"] == 230.0 and ps["2313122"]["price_eur"] == 5.1
    assert ps["2311070"]["price_eur"] == 13.7 and ps["2311070"]["size_g"] == 400.0      # single space before the weight
    assert ps["2310273"]["breikost"] is True
    assert "2390037" not in ps                                                          # weekly carton, no weight
    assert ps["2313225"]["overflow"] is True                                            # printed after the carton block

def test_parse_nutrition_and_flags():
    n = G.parse_nutrition(NT)
    a = n["2313122"]
    assert a["nutrition_100g"] == {"kcal": 36.0, "fat": 1.4, "satfat": 0.4, "carbs": 2.0, "sugar": 0.3, "protein": 3.7, "salt": 0.93}
    assert a["flags"] == ["D", "L", "LF", "SF"] and a["allergens"] == ["A", "C", "L"]
    assert n["2301698"]["nutrition_100g"]["kcal"] == 150.0                              # wrapped name line
    assert n["2313364"]["name"] == "Milchreis mit Beerenröster"                         # LVK GFLF suffix stripped
    assert set(n["2313364"]["flags"]) >= {"GF", "LF", "VEG"}

def test_join_meal_filter_and_overflow_category():
    ps = {p.source_id: p for p in G.join(G.parse_prices(PT), G.parse_nutrition(NT))}
    assert ps["2313122"].unit_price_eur == 22.17 and ps["2313122"].ean is None and ps["2313122"].image_url == G.catalog_photo("2313122")
    assert ps["2313225"].category == "Süßes zum Träumen" and ps["2313225"].extra["is_meal"]
    assert not ps["9510056"].extra["is_meal"]                                           # cake
    assert ps["2313364"].extra["vegetarian"] is True


def test_photos_from_media_exact_article_number_only():
    from food_connectors.adapters.gourmet_daheim import photos_from_media
    items = [
        {"date": "2021-01-17T10:00:00", "source_url": "https://www.mahlzeit.co.at/wp-content/uploads/2021/01/2310057_Rindsgulasch_Spaetzle_web_cropped.jpg.png"},
        {"date": "2021-01-30T10:00:00", "source_url": "https://www.mahlzeit.co.at/wp-content/uploads/2021/01/2310057_Rindsgulasch_Spaetzle_web-1.jpg"},
        {"date": "2021-01-17T10:00:00", "source_url": "https://www.mahlzeit.co.at/wp-content/uploads/2021/01/2311070_Schweinsmedaillons_web.jpg"},
        {"date": "2024-11-12T10:00:00", "source_url": "https://www.mahlzeit.co.at/wp-content/uploads/2024/11/2313512.jpg"},
        {"date": "2025-01-10T10:00:00", "source_url": "https://www.mahlzeit.co.at/wp-content/uploads/2025/01/Salbeihuhn_2023_quer_wb-scaled.jpeg"},
        {"date": "2020-04-01T10:00:00", "source_url": "https://www.mahlzeit.co.at/wp-content/uploads/2020/04/58418747-Mahlzeit-Stellengesuch.jpg"},
    ]
    ph = photos_from_media(items)
    assert ph == {"2310057": items[1]["source_url"], "2311070": items[2]["source_url"]}


def test_catalog_photo_fallback():
    from food_connectors.adapters import gourmet_daheim as G
    assert len(G.CATALOG_PHOTO_ARTS) == 127
    assert G.catalog_photo("2302034").endswith("/images/gourmet_daheim/2302034.jpg")
    assert G.catalog_photo("9999999") is None
