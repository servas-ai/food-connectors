import pathlib, re
from food_connectors.adapters import diechtl as D

FX = pathlib.Path(__file__).parent / "fixtures"


def test_category_filter():
    page = (FX / "diechtl_feinkost_im_glas.html").read_text()
    urls = D.category_urls(page)
    meals = [u for u in urls if D.is_meal(u)]
    assert len(urls) == 4 and meals == [D.BASE + "/rindsgulasch-im-glas"]
    # fallback without the ItemList JSON-LD still finds the same product links
    no_ld = re.sub(r'<script type="application/ld\+json">.*?</script>', "", page, flags=re.S)
    assert D.category_urls(no_ld) == urls


def test_rindsgulasch_from_jsonld():
    p = D.product(D.BASE + "/rindsgulasch-im-glas", (FX / "diechtl_rindsgulasch.html").read_text())
    assert p.name == "Rindsgulasch im Glas" and p.price_eur == 8.99 and p.size_g == 390.0 and p.unit_price_eur == 23.05
    assert p.source_id == "DI-GL-001" and p.extra["availability"] == "InStock"
    assert p.image_url.startswith(D.BASE + "/media/") and "5awdk5t8.png" in p.image_url
    assert p.nutrition_100g == {} and p.ean is None


def test_label_ingredients_only_for_known_image():
    page = (FX / "diechtl_rindsgulasch.html").read_text()
    p = D.product("rindsgulasch-im-glas", page)
    assert p.extra["ingredients"].startswith("50% Rind") and "SELLERIE" in p.extra["ingredients"]
    q = D.product("rindsgulasch-im-glas", page.replace("5awdk5t8.png", "newphoto.png"))
    assert q.extra["ingredients"] is None and q.extra["allergens"] is None
