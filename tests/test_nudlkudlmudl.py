import pathlib
from food_connectors.adapters import nudlkudlmudl as N

H = (pathlib.Path(__file__).parent / "fixtures" / "nudlkudlmudl" / "onlineshop.html").read_text()


def test_blocks_and_filter():
    names = [x["name"] for x in N.blocks(H)]
    assert len(names) == 10 and "Kärntner Kletzennudel" in names
    ps = N.all_products(H)
    assert len(ps) == 7 and not any(N.EXCLUDE.search(p.name) for p in ps)


def test_kasnudel():
    p = N.product("kaerntner-kasnudel", H)
    assert p.store == "Online: Martina's Nudlkudlmudl" and p.price_eur == 12.9 and p.size_g == 600.0 and p.unit_price_eur == 21.5
    assert p.extra["in_stock"] and p.extra["ingredients"].startswith("Bio Heumilchtopfen") and p.ean is None and p.nutrition_100g == {}
    assert "i0fbf0e60f81f6f65" in p.image_url


def test_unlabelled_ingredients_and_out_of_stock():
    s = N.product("Spinatnudel", H)
    assert s.extra["ingredients"].startswith("Bio Heumilchtopfen , Kartoffel, Blattspinat") and "Serviertipp" not in s.extra["ingredients"]
    b = N.product("baerlauchnudeln", H)
    assert b.extra["in_stock"] is False and b.price_eur == 12.9
    r = N.product("kaerntner-schweinsbraten", H)
    assert r.size_g == 250.0 and r.price_eur == 6.0 and r.unit_price_eur == 24.0 and r.extra["ingredients"] == "Schweinefleisch, Gewürze, Schweinefett, Senf"
    assert N.product("kletzennudel", H) is None
