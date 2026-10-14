import json, pathlib
from food_connectors.adapters import juit as J
RAW = json.loads((pathlib.Path(__file__).parent / "fixtures" / "juit_content_de.json").read_text())

def test_dishes_only_dish_entries():
    ds = J.dishes(data=RAW); assert len(ds) == 2 and all("title" in f for f in ds)

def test_to_product_tuna():
    p = J.to_product(next(f for f in J.dishes(data=RAW) if f["ean"] == "4063587710027"))
    assert p.source == "juit" and p.store == "Online: Juit" and p.brand == "Juit" and p.name == "High Protein Tuna Bolognese"
    assert p.size_g == 500 and p.nutrition_100g["kcal"] == 109 and p.nutrition_100g["protein"] == 9.4 and p.nutrition_100g["salt"] == 0.79
    assert p.price_eur is None  # prices behind login, never guessed
    assert p.image_url.startswith("https://cdn.juit.gmbh/") and p.source_url == "https://www.juit.com/de/gerichte/high-protein-tuna-pasta"
    assert p.extra["sellable"] is True and p.extra["portions"] == 2 and "THUNFISCH" in p.extra["ingredients"]

def test_unsellable_flag():
    ps = [J.to_product(f) for f in J.dishes(data=RAW)]
    assert sorted(p.extra["sellable"] for p in ps) == [False, True]

def test_text_flatten():
    doc = {"nodeType": "document", "content": [{"nodeType": "paragraph", "content": [{"nodeType": "text", "value": "a"}, {"nodeType": "text", "value": "b"}]}]}
    assert J._text(doc) == "ab"
