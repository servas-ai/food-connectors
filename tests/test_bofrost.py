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
    assert b.is_starter_url(base + "pizza-snacks_44198/snacks_44195/salami-pizzettis_00336.html")
    assert b.is_starter_url(base + "pizza-snacks_44198/snacks_44195/broccoli-laibchen_03726.html")
    assert not b.is_starter_url(base + "pizza-snacks_44198/snacks_44195/camembert-paniert_01271.html")
    assert b.is_meal_url(base + "schlemmerfilet-gourmet-extra-knusprig_01502.html")
    # default ready-meal filter unchanged: desserts stay out
    assert not b.is_meal_url(base + "suesse-vielfalt_44201/suessspeisen-desserts_48009/kaiserschmarrn_01575.html")


def test_off_gtin_article_weight_nutrition():
    import json
    off = json.loads((pathlib.Path(__file__).parent / "fixtures" / "off_bofrost_gtin.json").read_text())
    assert B.barcode_article("0836069004150") == "00415" and B.barcode_article("0836069004151") is None
    assert B.barcode_article("00020047") is None  # short internal article code, not a GTIN
    from food_connectors.schema import Product
    mk = lambda art, name, g, n: Product(source="bofrost", store="Online: bofrost*", source_id=art, name=name, size_g=g, nutrition_100g=n,
                                         source_url=f"https://www.bofrost.at/shop/x_1/y_2/z_{art}.html")
    cw = mk("00415", "Currywurst", 800, {"kcal": 197.0, "protein": 7.2, "fat": 13.6, "carbs": 11.1})
    assert B.off_gtin(cw, off) == "0836069004150"
    rp = mk("00667", "Röstipfanne", 1000, {"kcal": 129.0, "protein": 5.7, "fat": 5.9, "carbs": 11.9})
    assert B.off_gtin(rp, off) == "0045469006675"  # "1.000g" parsed as 1000 g
    hr = mk("01279", "Hühner-Rahmpfanne", 1000, {"kcal": 134.0, "protein": 6.9})
    assert B.off_gtin(hr, off) == "0836069012797"  # OFF without nutrition: article + weight
    bg = mk("01601", "Bami Goreng", 1000, {"kcal": 114.0, "protein": 7.5, "fat": 3.3, "carbs": 12.6})
    assert B.off_gtin(bg, off) is None  # carbs 12.6 vs 11.6 > 5 %
    tc = mk("11292", "Tandoori Chicken mit Basmati-Reis", 400, {"kcal": 181.0})
    assert B.off_gtin(tc, off) is None  # OFF has no net weight
    sp = mk("01782", "LA PIZZA Speciale", 838, {"kcal": 211.0})
    assert B.off_gtin(sp, off) is None  # OFF 425 g (single pizza) vs 838 g pack
