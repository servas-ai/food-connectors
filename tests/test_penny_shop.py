import json, pathlib
from food_connectors.adapters import penny_shop as P
RAW = json.loads((pathlib.Path(__file__).parent / "fixtures" / "penny_listing.json").read_text())
BY = {r["sku"]: r for r in RAW["results"]}

def test_to_product_meal():
    p = P.to_product(BY["78-790129"])
    assert p.source == "penny-shop" and p.store == "PENNY" and p.brand == "Ich bin Österreich"
    assert p.name == "Wiener Schnitzel*" and p.price_eur == 4.99 and p.size_g == 750
    assert "Tiefkühl > Fertiggerichte" in p.category and p.image_url.startswith("https://images.cdn.europe-west1.gcp.commercetools.com/")
    assert p.source_url == "https://www.penny.at/produkte/" + BY["78-790129"]["slug"] and p.extra["rewe_article"] == "790129"
    assert P.is_ready_meal(p)

def test_offer_categories_dropped_and_not_meal():
    for sku in ("78-107921", "78-284508", "78-102699", "78-599272"):  # Würze, Brühe, Sauerkraut, Pommes
        p = P.to_product(BY[sku]); assert "ngebot" not in (p.category or ""); assert not P.is_ready_meal(p), p.name

def test_schnelle_kueche_and_pizza():
    assert P.is_ready_meal(P.to_product(BY["78-785625"])) and P.is_ready_meal(P.to_product(BY["78-913024"]))
    p = P.to_product(BY["78-913024"]); assert p.size_g == 720 and p.extra["variants"] == "div. Sorten"

def test_fetch_offline(monkeypatch):
    monkeypatch.setattr(P, "get", lambda url, timeout=30: RAW)
    ps = P.PennyShop().fetch()
    ids = {p.source_id for p in ps}
    assert {"78-790129", "78-785625", "78-913024", "78-780413"} <= ids and "78-107921" not in ids

def test_product_lookup_offline(monkeypatch):
    seen = []
    monkeypatch.setattr(P, "get", lambda url, timeout=30: seen.append(url) or BY["78-785625"])
    p = P.product("785625")
    assert seen == [P.API + "/78-785625"] and p.source_id == "78-785625" and p.price_eur == 4.99 and p.size_g == 400
