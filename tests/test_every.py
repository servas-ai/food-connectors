import json, pathlib
from food_connectors.adapters import every as E
FX = pathlib.Path(__file__).parent / "fixtures"
H = (FX / "every_creamy-peanut-curry.html").read_text()
SP = json.loads((FX / "every_products.json").read_text())["products"][0]

def test_blok_and_product():
    b = E.product_blok(H)
    assert b and b["component"] == "product" and b["product_weight"] == "450"
    p = E.to_product(SP, b)
    assert p.source == "every" and p.store == "Online: every." and p.brand == "every." and p.name == "Creamy Peanut Curry"
    assert p.price_eur == 9.99 and p.size_g == 450 and p.unit_price_eur == 22.2 and p.unit == "kg"
    assert p.nutrition_100g == {"kcal": 114.0, "fat": 5.2, "satfat": 1.9, "carbs": 10.4, "sugar": 1.9, "fiber": 1.6, "protein": 5.5, "salt": 0.73}
    assert p.extra["pack_nutrition"]["kcal"] == 513.0 and p.extra["pack_nutrition"]["protein"] == 24.7
    assert p.ean is None and p.source_id == "F5001Z" and p.image_url.startswith("https://cdn.shopify.com/")
    assert "für AT: Fisolen" in p.extra["ingredients"] and "MIKROWELLE" in p.extra["preparation"]
    assert p.extra["vegan"] is True and p.extra["available"] is True
    assert E.is_ready_meal(p)

def test_is_meal_filters():
    hs = {"creamy-peanut-curry"}
    assert E.is_meal(SP, hs)
    assert not E.is_meal(SP, {"other"})
    assert not E.is_meal({**SP, "product_type": "Add-on"}, hs)
    free = {**SP, "variants": [{**SP["variants"][0], "price": "0.00"}]}
    assert not E.is_meal(free, hs)
    assert not E.is_meal({**SP, "handle": "test-produkt", "title": "Test"}, {"test-produkt"})

def test_sitemap_handles():
    xml = ("<urlset><url><loc>https://every-foods.com/products/creamy-peanut-curry</loc></url>"
           "<url><loc>https://every-foods.com/en/products/creamy-peanut-curry</loc></url></urlset>")
    assert E.sitemap_handles(xml) == {"creamy-peanut-curry"}

def test_missing_blok_keeps_nulls():
    p = E.to_product(SP, None)
    assert p.size_g is None and p.nutrition_100g == {} and not E.is_ready_meal(p)

def test_english_labels_and_pack_check():
    doc = {"type": "doc", "content": [{"type": "table", "content": [
        {"type": "tableRow", "content": [{"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": t}]}]} for t in ("Typical values", "100g", "Portion (400g)")]}] + [
        {"type": "tableRow", "content": [{"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": t}]}]} for t in row]}
        for row in (("Energy (kj/kcal)", "625/149", "2498/597"), ("Fat (g)", "5,9", "23,6"), ("of which saturated fatty acids (g)", "1", "4"),
                    ("Carbohydrates (g)", "17,8", "71,2"), ("of which sugar (g)", "3,2", "12,8"), ("Dietary fiber (g)", "4,4", "17,6"),
                    ("Protein (g)", "4,1", "1,4"), ("Salt (g)", "0,8", "3,19"))]}]}
    per100, pack, per = E.nutrition_table(doc)
    assert per == "100g" and per100 == {"kcal": 149.0, "fat": 5.9, "satfat": 1.0, "carbs": 17.8, "sugar": 3.2, "fiber": 4.4, "protein": 4.1, "salt": 0.8}
    assert E.pack_check(per100, pack, 400) == ["protein"]
