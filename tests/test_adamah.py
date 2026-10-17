import json, pathlib
from food_connectors.adapters import adamah as A

FX = pathlib.Path(__file__).parent / "fixtures"

def _j(n): return json.loads((FX / n).read_text(encoding="utf-8"))

def test_meal_filter_on_search_sample():
    ps = {p["sid"]: p for p in _j("adamah_search_sample.json")}
    assert A.is_meal(ps[42093])            # Hartls Rindsgulasch im Weckglas (0841)
    assert A.is_meal(ps[68890])            # Venatio Wildragout
    assert A.is_meal(ps[70905])            # Soto Buritto-Röllchen (0275)
    assert not A.is_meal(ps[68889])        # Hirschsugo = sauce
    assert not A.is_meal(ps[66988])        # Pastete
    assert not A.is_meal(ps[71502])        # Cheesecake = dessert
    assert not A.is_meal(ps[11260])        # Weizen Schnitzel = patty

def test_dish_in_sauce_is_meal():
    assert A.is_meal({"name": "Wilde Fleischbällchen in Tomatensauce", "category": "0841"})
    assert not A.is_meal({"name": "Wildschweinsugo mit Paradeisern", "category": "0841"})

def test_detail_to_product_hartl():
    p = A.to_product(_j("adamah_detail_42093.json"))
    assert p.store == A.STORE and p.price_eur == 11.9 and p.size_g == 460.0
    assert p.ean is None and p.extra["plu"] == "83255"          # internal PLU never mapped to GTIN
    assert p.image_url.startswith("https://www.adamah.at/ACM/AttachmentLoader?rowguid=")
    assert p.extra["bio"] is True and "Rindfleisch" in p.extra["ingredients"]
    assert p.nutrition_100g == {}

def test_achleitner_jar_volume_not_taken():
    p = A.to_product(_j("adamah_detail_67256.json"))
    assert p.size_g is None and "Glasvolumen" in p.extra["size_note"]
    assert p.producer == "Biohof Achleitner" and p.price_eur == 8.2
