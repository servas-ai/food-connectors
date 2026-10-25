import pathlib
from food_connectors.adapters import bauernladen as B, ADAPTERS

FX = pathlib.Path(__file__).parent / "fixtures"


def test_listing_urls_and_pages():
    ts, n = B.parse_listing((FX / "bauernladen_list1.html").read_text())
    assert n == 4 and len(ts) == 23
    t = next(t for t in ts if t["id"] == "27303")
    assert t["producer_slug"] == "fairkocht" and t["url"] == "https://bauernladen.at/produkte/fairkocht/chili-con-carne-27303"


def test_hirschchili_jsonld_size_producer():
    p = B.parse_product((FX / "bauernladen_hirschchili_39804.html").read_text())
    assert p.source == "bauernladen" and p.name == "Hirschchili" and p.price_eur == 8.5
    assert p.size_g == 320.0 and p.unit == "g" and p.ean is None and p.nutrition_100g == {}
    assert p.brand == "Christöphl Manufaktur" and p.extra["producer_address"] == "Sukdull 13 8410 Wildon Steiermark"
    assert p.extra["availability"] == "InStock" and p.source_id == "39804"
    assert "Österreich" in p.extra["delivery_terms"] and p.image_url.endswith("Hirschchili.png")


def test_stk_offer_takes_size_from_name_and_keeps_nutrition_text():
    p = B.parse_product((FX / "bauernladen_kuerbiscremesuppe.html").read_text())
    assert p.size_g == 440.0 and p.unit == "ml" and p.price_eur == 6.99
    assert p.extra["nutrition_text"].startswith("Brennwert: 293 kJ / 70 kcal") and p.nutrition_100g == {}


def test_meal_filter():
    for n in ["Chili con Carne", "Kalbsbeuschel", "Wilde Fleischbällchen in Tomatensauce mit Bio-Zutaten", "Hühnersuppe", "Vegie Chili"]:
        assert B.is_meal_name(n), n
    for n in ["Gemüsefond", "Klare Kalbssuppe", "kräftige Rindsuppe 1 Liter", "Kalbssugo", "Bio Sauce Bolonese", "Kaspressknödel",
              "Sauerkraut", "Kartoffelgratin", "Nusszelten", "Brunchbox Deluxe für 3-4 Personen", "Tafelspitzsülzchen im Glas",
              "Wurzers Power Berry Erdbeer-Kürbiskern-Proteinpulver", "Letscho vegan, glutenfrei im Glas eingekocht"]:
        assert not B.is_meal_name(n), n


def test_registered():
    assert ADAPTERS["bauernladen"].status == "live"


def test_fairkocht_nutrition_offline():
    import json, pathlib
    from food_connectors.adapters.bauernladen import fairkocht_nutrition
    fx = json.loads((pathlib.Path(__file__).parent / "fixtures/fairkocht_store_api_sample.json").read_text(encoding="utf-8"))
    n = fairkocht_nutrition(fx)
    g = n["Gulaschsuppe"]
    assert g["kcal_100"] == 82 and g["protein_100"] == 6.7 and g["salt_100"] == 1.1 and g["atwater_ok"]
    assert g["price_eur"] == 15.5 and g["size"] == "680 g"
    assert n["Paprikahendl"]["atwater_ok"] is False
