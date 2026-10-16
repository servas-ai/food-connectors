import json, pathlib
from food_connectors.adapters import denns as D
RAW = json.loads((pathlib.Path(__file__).parent / "fixtures" / "denns_offers.json").read_text())

def test_offers_dedup_at():
    ns = D.offers(RAW); assert ns and all(n["land"] == "at" for n in ns)
    assert len({n["_id"] for n in ns}) == len(ns)

def test_to_product_soup():
    p = next(D.to_product(n) for n in D.offers(RAW) if n["itemno"] == "564131")
    assert p.source == "denns" and p.store == "denn's BioMarkt" and p.brand == "MyDeli"
    assert p.price_eur == 3.49 and p.extra["regular_price_eur"] == 3.99 and p.size_g is None  # '350 g / 380 g' range
    assert p.extra["valid_from"] == "2026-10-07" and p.extra["valid_to"] == "2026-10-20" and p.extra["price_from"] is True
    assert p.image_url == "https://images.dennree.de/fitinto/576x384/564131.top.png" and D.is_ready_meal(p)

def test_frozen_single_pack():
    p = next(D.to_product(n) for n in D.offers(RAW) if n["itemno"] == "003115")
    assert p.size_g == 200 and p.unit_price_eur == 21.45 and p.unit == "kg" and p.extra["frozen"] and p.name == "followfood Airfryer Fish Nuggets"

def test_not_meal():
    p = next(D.to_product(n) for n in D.offers(RAW) if n["itemno"] == "191711")
    assert not D.is_ready_meal(p)

def test_size():
    assert D._size("je 200 g") == 200 and D._size("1 kg") == 1000 and D._size("185 g - 200 g") is None and D._size("Stück") is None

# T2336: dennree brand catalog, Neu im Sortiment, bistro lunch menu (offline fixtures)
FX = pathlib.Path(__file__).parent / "fixtures"

def test_dennree_list():
    its = D.dennree_list("pizza", (FX / "dennree_cat_pizza.html").read_text())
    assert [i["itemno"] for i in its] == ["041534", "040228"]
    assert its[1]["url"].endswith("/pizza/al-forno-pizza-spinat") and its[1]["name"] == "Al Forno Pizza Spinat"

def test_dennree_product_nutrition_atwater():
    url = "https://www.dennree.de/dennree-produkte/uebersicht/pizza/al-forno-pizza-spinat"
    p = D.dennree_product(url, (FX / "dennree_pizza_spinat.html").read_text())
    assert p.name == "dennree Al Forno Pizza Spinat" and p.brand == "dennree" and p.size_g == 350 and p.source_id == "040228"
    assert p.nutrition_100g == {"kcal": 200.0, "fat": 6.1, "satfat": 2.5, "carbs": 27.0, "sugar": 2.6, "protein": 7.6, "salt": 1.1}
    assert p.extra["atwater_ok"] is True and p.extra["frozen"] and p.price_eur is None and p.ean is None
    assert p.image_url == "https://images.dennree.de/fitinto/576x384/040228.front.png"
    assert p.extra["ingredients"].startswith("WEIZENMEHL*") and "Sellerie" in p.extra["notes"]

def test_atwater_reject():
    assert D.atwater_ok({"kcal": 500, "fat": 1, "carbs": 10, "protein": 5}) is False
    assert D.atwater_ok({"kcal": 200}) is None

def test_placeholder_image():
    assert D.is_placeholder((FX / "dennree_placeholder.png").read_bytes()) and not D.is_placeholder(b"x")

def test_new_products_at():
    ps = D.new_products(json.loads((FX / "denns_neu_im_sortiment.json").read_text()))
    p = next(p for p in ps if "Piccoli" in p.name)
    assert p.name == "followfood Piccoli Tomate & Mozzarella" and p.price_eur == 6.29 and p.size_g == 270
    assert p.image_url.startswith("https://cdn.sanity.io/images/or2m2oma/production/0d7b60e5")

def test_lunch_menu():
    r = D.lunch_menu("linz-kaisergasse-17", json.loads((FX / "denns_lunch_linz-kaisergasse-17.json").read_text()))
    assert len(r) == 32 and sum(x["next_week"] for x in r) == 16
    x = r[0]; assert x["dish"] == "Vegane Rote-Linsen-Suppe" and x["price_eur"] == 3.9 and x["day"] == "2026-10-12" and x["vegan"]
