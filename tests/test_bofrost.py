import pathlib
from food_connectors.adapters import bofrost as B
H = (pathlib.Path(__file__).parent / "fixtures" / "bofrost_product_00196.html").read_text()
URL = "https://www.bofrost.at/shop/gefluegel_41809/gefluegelzubereitungen_41810/huehnerbrustfilet-in-exotischer-currysauce_00196.html"

def test_parse_product_curry():
    p = B.parse_product(H, URL)
    assert p.source == "bofrost" and p.store == "Online: bofrost*" and p.name == "Hühnerbrustfilet in exotischer Currysauce"
    assert p.price_eur == 13.99 and p.size_g == 600 and p.unit_price_eur == 23.32 and p.unit == "kg"
    assert p.nutrition_100g == {"kcal": 93.0, "fat": 3.1, "satfat": 2.2, "carbs": 6.6, "sugar": 3.2, "fiber": 0.9, "protein": 9.1, "salt": 0.93}
    assert p.ean is None and p.source_id == "00196" and p.image_url.startswith("https://www.bofrost.at/medias/00196-AT-")
    assert p.category == "Geflügel > Geflügelzubereitungen" and p.extra["portions"] == 2 and "Hühnerbrustinnenfilet" in p.extra["ingredients"]
    assert p.extra["availability"] == "InStock" and B.is_ready_meal(p)

def test_urls_and_meal_filter():
    xml = ("<urlset><url><loc>" + URL + "</loc></url><url><loc>https://www.bofrost.at/shop/eis_42743/eisdesserts_37993/eiskonfekt-bourbon-vanille_00068.html</loc></url>"
           "<url><loc>https://www.bofrost.at/shop/pfannengerichte-pasta_42741/pasta_48016/lasagne_01234.html</loc></url></urlset>")
    us = B.product_urls(product_xml=xml); assert len(us) == 3
    assert [B.is_meal_url(u) for u in us] == [True, False, True]
    assert B.article_no(us[2]) == "01234"


def test_course_url_filters():
    from food_connectors.adapters import bofrost as b
    base = "https://www.bofrost.at/shop/"
    assert b.is_warm_dessert_url(base + "suesse-vielfalt_44201/suessspeisen-desserts_48009/kaiserschmarrn_01575.html")
    assert b.is_warm_dessert_url(base + "suesse-vielfalt_44201/suessspeisen-desserts_48009/mini-germknoedel_03544.html")
    assert not b.is_warm_dessert_url(base + "suesse-vielfalt_44201/suessspeisen-desserts_48009/blaetterteig_03290.html")
    assert not b.is_warm_dessert_url(base + "suesse-vielfalt_44201/torten-tortenstuecke_39770/donauwellen_11872.html")
    assert not b.is_warm_dessert_url(base + "eis_42743/eisdosen_34984/free-bourbon-vanille-eiscreme_10103.html")
    assert b.is_starter_url(base + "pizza-snacks_44198/snacks_44195/bo-fruehlingsrollen_01607.html")
    assert b.is_starter_url(base + "hausmannskost-suppen_44200/suppen-suppeneinlagen_48005/kaspressknoedel_03913.html")
    assert not b.is_starter_url(base + "pizza-snacks_44198/snacks_44195/gouda-ringe_18009.html")
    # default ready-meal filter unchanged: desserts stay out
    assert not b.is_meal_url(base + "suesse-vielfalt_44201/suessspeisen-desserts_48009/kaiserschmarrn_01575.html")
