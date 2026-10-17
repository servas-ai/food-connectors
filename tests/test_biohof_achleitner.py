import pathlib
from food_connectors.adapters import biohof_achleitner as B, ADAPTERS

FX = pathlib.Path(__file__).parent / "fixtures"
CAT = (FX / "biohof_hausgmocht_category.html").read_text()


def test_category_tiles_and_filter():
    ts = B.parse_category(CAT)
    assert len(ts) == 28
    meals = [t for t in ts if B.is_meal_name(t["name"])]
    assert len(meals) == 13
    names = {t["name"] for t in meals}
    assert "Hausg'mocht Rindsgulasch" in names and "Hausg'mocht Linsen Moussaka 400g" in names
    assert not any(B.is_meal_name(n) for n in ["Hausg'mocht Sugo", "Hausg'mocht Grünkernbolognese", "Hausg'mocht Klare Rindssuppe",
                                               "Hausg'mocht gemischtes Paket", "Hausg'mocht Fruchtaufstrich Marille"])
    t = next(t for t in ts if t["id"] == "4754")
    assert t["price_eur"] == 6.8 and "vegan" in t["labels"] and t["orderable"]


def test_product_rindsgulasch():
    t = next(t for t in B.parse_category(CAT) if t["id"] == "4755")
    p = B.parse_product((FX / "biohof_rindsgulasch_4755.html").read_text(), t["url"], t)
    assert p.source == "biohof-achleitner" and p.store == "Online: Biohof Achleitner"
    assert p.price_eur == 8.7 and p.size_g == 350.0 and p.ean is None and p.nutrition_100g == {}
    assert p.extra["ingredients"].startswith("Gemüsefond*") and p.extra["mehrweg"] and p.extra["bio"]
    assert p.image_url.endswith("/uploadPim/4755/001_023505-thumbnail-520-520.jpg")


def test_size_rules():
    ts = {t["id"]: t for t in B.parse_category(CAT)}
    m = B.parse_product((FX / "biohof_moussaka_4759.html").read_text(), ts["4759"]["url"], ts["4759"])
    assert m.size_g == 400.0 and m.extra["size_note"] == "Menge aus dem Produktnamen" and m.extra["available_window"] == "19.10. - 31.10."
    r = B.parse_product((FX / "biohof_ruebengulasch_2560.html").read_text(), ts["2560"]["url"], ts["2560"])
    assert r.size_g is None and "Glasvolumen" in r.extra["size_note"]  # '410ml Glas' is the jar, not the content


def test_registered():
    assert ADAPTERS["biohof-achleitner"].status == "live"
