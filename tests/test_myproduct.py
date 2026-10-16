import pathlib
from food_connectors.adapters import myproduct as M

FX = pathlib.Path(__file__).parent / "fixtures"


def _p(name, key):
    return M.parse_product((FX / name).read_text(), f"https://myproduct.at/{key}")


def test_bolognese_parses_nutrition_but_is_sauce_component():
    p = _p("myproduct_bolognese-rind-400g.html", "bolognese-rind-400g-hartls-kulinarikum")
    assert p.source == "myproduct" and p.store == "Online: myProduct"
    assert p.brand == "Hartls Kulinarikum" and p.price_eur and p.size_g == 400.0
    n = p.nutrition_100g
    assert n["kcal"] == 83.0 and n["fat"] == 4.1 and n["sugar"] == 2.7 and n["protein"] == 4.2 and n["salt"] == 1.2
    assert p.ean and M.valid_ean(p.ean) == p.ean
    assert "Linz" in (p.producer or "") and p.image_url.startswith("https://myproduct.at/media/catalog/product/")
    assert "brandpersonality" not in p.image_url
    assert p.extra["exclusion"] and not M.is_ready_meal(p)  # Bolognese without pasta = sauce component (as TANN Rindsbolognese)


def test_soup_without_nutrition_is_not_estimated():
    p = _p("myproduct_bio-rindsuppe-390g.html", "bio-rindsuppe-390g-hartls-kulinarikum")
    assert p.ean == "9120058832581" and p.size_g == 390.0 and p.price_eur == 6.29
    assert p.nutrition_100g == {} and "keine Nährwertkennzeichnung" in p.extra["nutrition_label"]
    assert p.extra["bio"] is True and p.extra["ingredients"].startswith("Wasser")


def test_category_datalayer():
    items = M.parse_category((FX / "myproduct_category_p1.html").read_text())
    assert len(items) == 42 and all(i["sku"] and i["url"] and i["price"] for i in items)
    assert items[0]["brand"] == "Hartls Kulinarikum"


def test_exclusions():
    assert M.exclusion("Bio Kalbsfond 190g - Fertiggericht von Hartls Kulinarikum")
    assert M.exclusion("Bio Rillettes vom Schlierbacher Wildhendl 170g")
    assert M.exclusion("Bio Demeter Gemüseburger Fertigmischung 160g")
    assert M.exclusion("Bio Chili con Carne 30g von Lebensbaum")
    assert M.exclusion("Bio Indische Bulgur-Pfanne 150g - 6er Vorteilspack", "BULGUR*, Gemüse getrocknet*") 
    assert M.exclusion("Bio Dolmas Weinblätter gefüllt 280g - 6er Vorteilspack", "gekochter Reis* (Wasser, Reis*)") is None
    assert M.exclusion("Bio Chili Con Carne 460g - Fertiggericht von Hartls Kulinarikum", "Rindfleisch, Bohnen") is None
    assert M.exclusion("Bio Spaghetti Bolognese 35g von Lebensbaum")  # Würzbeutel
    assert M.exclusion("Bio Rice Ramen Tom Yum 72g - 8er Vorteilspack") is None
    assert M.exclusion("Bio Risotto mit Kürbis 250g - 8er Vorteilspack", "Carnaroli Reis* 90% , Kürbis* 6% , Meersalz")
    assert M.exclusion("Bio Feinkostsauce dunkel für 2l 200g - 6er Vorteilspack")
    assert M.exclusion("Bio Ravioli in Tomatensauce 350g - 6er Vorteilspack", "Wasser, Tomaten") is None
    assert M.exclusion("Molke Suppe Gemüseteller 500g", "Süßmolkepulver, Speisesalz, Hefeextrakt")
    assert M.exclusion("Bio Rinderknochenbrühen Konzentrat 440g - 6er Vorteilspack", "Wasser, Rinderknochen")
    assert M.exclusion("Bio Sonnenblumenhack 500g von Sunflowerfamily", "Sonnenblumenprotein")
    assert M.atwater_check({"kcal": 83, "fat": 4.1, "carbs": 7.0, "protein": 4.2}) == "ok"
    assert M.atwater_check({"kcal": 300, "fat": 1, "carbs": 5, "protein": 2}) == "atwater_mismatch"
    assert M.unit_size_g("Bio Linseneintopf 350g - 6er Vorteilspack") == 350 and M.pack_count("Bio Linseneintopf 350g - 6er Vorteilspack") == 6


def test_ean_check_digit():
    assert M.valid_ean("9120058832581") == "9120058832581"
    assert M.valid_ean("9120058832582") is None and M.valid_ean("") is None
