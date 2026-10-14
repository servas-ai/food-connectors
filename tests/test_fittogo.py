import pathlib
from food_connectors.adapters import fittogo as F

H = (pathlib.Path(__file__).parent / "fixtures" / "fittogo_bbq.html").read_text()
URL = "https://fittogo.at/products/high-protein-bbq-chicken-mit-mac-cheese"

def test_parse_bbq():
    p = F.parse_product(H, URL)
    assert p.source == "fittogo" and p.store == "Online: Fit2go" and p.brand == "fit2go.meals"
    assert p.name == "High Protein BBQ Chicken mit Mac & Cheese"
    assert p.size_g == 400 and p.price_eur == 9.99
    assert p.nutrition_100g["kcal"] == 144.0 and p.nutrition_100g["protein"] == 14.0
    assert p.nutrition_100g["carbs"] == 13.0 and p.nutrition_100g["fat"] == 4.0
    assert p.extra["pack_nutrition"] == {"kcal": 576.0, "protein": 56.0, "carbs": 52.0, "fat": 16.0}
    assert p.image_url.startswith("https://cdn.shopify.com/") and p.source_id == "high-protein-bbq-chicken-mit-mac-cheese"
    assert F.is_ready_meal(p)

def test_urls_filter_boxes():
    xml = ("<urlset>"
           "<url><loc>https://fittogo.at/products/high-protein-bbq-chicken-mit-mac-cheese</loc></url>"
           "<url><loc>https://fittogo.at/products/12er-meal-box</loc></url>"
           "<url><loc>https://fittogo.at/products/thai-red-curry-mit-sojageschnetzeltem-und-reisnudeln</loc></url>"
           "<url><loc>https://fittogo.at/products/musterpaket</loc></url>"
           "</urlset>")
    us = F.product_urls(sitemap_xml=xml)
    assert us == [
        "https://fittogo.at/products/high-protein-bbq-chicken-mit-mac-cheese",
        "https://fittogo.at/products/thai-red-curry-mit-sojageschnetzeltem-und-reisnudeln",
    ]
    assert F.is_meal_url(us[0]) and not F.is_meal_url("https://fittogo.at/products/12er-meal-box")
