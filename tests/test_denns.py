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
