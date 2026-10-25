import pathlib
from food_connectors.adapters import moakt as M

D = pathlib.Path(__file__).parent / "fixtures" / "moakt"
PAGES = {("/" + f.stem[2:]) if f.stem.startswith("v_") else "/" + f.stem: f.read_text() for f in D.glob("*.html")}


def test_grid_and_filter():
    names = [g["name"] for g in M.grid(PAGES["/qualitaetsfleischerei-feiertag"])]
    assert len(names) == 22 and "mein Glas - Rinder-Gulaschsaft essfertig 400g" in names
    assert not M.is_meal("mein Glas - Rinder-Kraftsuppe essfertig 400g") and not M.is_meal("Sugo Bolgonese mit Wild")
    ps = M.all_products(PAGES)
    assert len(ps) == 15 and len({p.source_id for p in ps}) == 15
    assert sum(1 for p in ps if p.image_url) == 13


def test_feiertag_gulasch():
    p = M.product("r-gulasch-essfertig-400g-pro-1-glas", PAGES)
    assert p.store == "Online: Moakt.at (Weiz)" and p.name == "Rinder-Gulasch essfertig 400g"
    assert p.price_eur == 8.1 and p.size_g == 400.0 and p.unit_price_eur == 20.25 and p.ean is None and p.nutrition_100g == {}
    assert p.extra["ingredients"].startswith("Rindfleisch (32%)") and "656834929532487dad73734b" in p.image_url


def test_ml_and_no_size():
    w = M.product("wels-curry", PAGES)
    assert w.size_g == 430.0 and w.unit == "l" and w.price_eur == 9.1
    r = M.product("rinderragout", PAGES)
    assert r.brand == "Robert kocht" and r.size_g is None and r.unit_price_eur is None and r.price_eur == 8.5
    z = M.product("zwiebelsuppe", PAGES)
    assert z.image_url is None and z.price_eur == 9.0
