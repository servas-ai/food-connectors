import pathlib
from food_connectors.adapters import fichtenbauer as F

FX = pathlib.Path(__file__).parent / "fixtures"


def test_shop_filter():
    urls = F.shop_urls((FX / "fichtenbauer_shop.html").read_text())
    meals = sorted(u.rsplit("/", 1)[-1] for u in urls if F.is_meal(u))
    assert len(urls) == 21 and meals == ["beuschel-essfertig", "rindsgulasch-essfertig", "wildragout-essfertig"]


def test_rindsgulasch_microdata():
    p = F.product("rindsgulasch-essfertig", (FX / "fichtenbauer_rindsgulasch.html").read_text())
    assert p.name == "Rindsgulasch essfertig" and p.price_eur == 6.9 and p.size_g == 400.0 and p.unit_price_eur == 17.25
    assert p.extra["unit_price_eur_100g_shop"] == 1.73 and p.extra["ingredients"].startswith("Rindfleisch, Zwiebel")
    assert p.image_url == F.BASE + "/assets/images/3/gulasch-a85db27b-d8b30e7f.jpg"
    assert p.nutrition_100g == {} and p.ean is None


def test_non_jar_and_challenge_pages_are_skipped():
    page = (FX / "fichtenbauer_rindsgulasch.html").read_text()
    assert F.parse(page.replace("im 400g Glas", "900g"), F.SHOP + "/x") is None
    assert F.parse("<html>Please wait while your request is being verified...</html>", F.SHOP + "/x") is None
