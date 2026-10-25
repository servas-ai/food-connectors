import pathlib
from food_connectors.adapters import buchberger as B

FX = pathlib.Path(__file__).parent / "fixtures"


def test_category_filter():
    urls = B.category_urls((FX / "buchberger_essen_im_glas.html").read_text())
    meals = [u for u in urls if B.is_meal(u)]
    assert len(urls) == 8 and len(meals) == 5
    assert not any("sugo" in u or "gulaschsaft" in u or "bolognese" in u for u in meals)


def test_hirschragout_nutrition_as_printed():
    u = B.BASE + "/buchberger-hausgemachtes-hirschragout-im-glas-450-ml"
    p = B.product(u, (FX / "buchberger_hirschragout.html").read_text())
    assert p.price_eur == 13.5 and p.size_g == 450.0 and p.unit_price_eur == 3.0
    assert p.nutrition_100g == {"energy_kj": 578.0, "energy_kcal": 138.0, "protein_g": 9.3, "carbs_g": 11.0, "fat_g": 1.0}
    assert p.extra["atwater"]["ok"] is False and p.extra["ingredients"].startswith("Hirschfleisch")
    assert p.image_url.startswith("https://public.jolioo.com/") and p.ean is None


def test_rindsgulasch_without_nutrition():
    u = B.BASE + "/buchberger-hausgemachtes-rindsgulasch-im-glas-450-ml"
    p = B.product(u, (FX / "buchberger_rindsgulasch.html").read_text())
    assert p.price_eur == 8.3 and p.nutrition_100g == {} and p.extra["allergens"] == "enthält A und L"
    assert p.extra["mhd"].startswith("60 TAGE") or "60" in (p.extra["mhd"] or "")
