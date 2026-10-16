import json, pathlib
from food_connectors.open_prices import parse
FX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "open_prices_by_ean.json").read_text())

def test_parse_at_receipt():
    rows = parse(FX["4099200013312"], country="AT")
    assert rows and rows[0]["country"] == "AT" and rows[0]["currency"] == "EUR"
    assert rows[0]["shop"] == "Hofer" and rows[0]["proof_type"] == "RECEIPT"
    assert rows[0]["date"] == "2024-06-06" and rows[0]["price"] == 1.69

def test_country_and_since_filters():
    assert parse(FX["4056489706939"], country="AT") == []
    de = parse(FX["4056489706939"], country="DE")
    assert len(de) == 2 and de[0]["date"] >= de[1]["date"]
    assert parse(FX["4056489706939"], since="2026-07-20")[0]["date"] == "2026-07-22"
