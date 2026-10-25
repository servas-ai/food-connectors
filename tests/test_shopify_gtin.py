from food_connectors.adapters import shopify_gtin as S
from food_connectors.adapters import deflorian as D
from food_connectors.schema import Product


def test_valid_gtin():
    assert S.valid_gtin("9120035592651") and S.valid_gtin("4262398292221") and S.valid_gtin("0724754246773")
    assert not S.valid_gtin("9120035592652") and not S.valid_gtin("") and not S.valid_gtin("abc") and not S.valid_gtin("0000000000000")
    assert S.gtin({"barcode": " 9120035592651 "}) == "9120035592651" and S.gtin({"barcode": "123"}) is None and S.gtin(None) is None


def test_merge_into_products_json_entry_offline():
    sp = {"handle": "x", "title": "Kaspressknödel vorgebacken", "variants": [{"id": 11, "barcode": None, "price": "8.90", "grams": 400}, {"id": 12, "barcode": ""}]}
    S.merge_barcodes(sp, {"11": "9120035592651"})
    assert sp["variants"][0]["barcode"] == "9120035592651" and sp["variants"][1]["barcode"] == ""
    assert D.to_product(sp).ean == "9120035592651"


def _p(name, ean):
    return Product(source="t", store="s", name=name, brand=None, price_eur=None, unit_price_eur=None, unit=None,
                   size_g=None, nutrition_100g={}, ean=ean, image_url=None, producer=None, origin=None, category=None,
                   source_url=None, source_id=None, extra={})


def test_drop_shared_placeholder():
    ps = S.drop_shared([_p("Ragout", "0660357208391"), _p("Beuschel", "0660357208391"), _p("Curry", "9120035592385"), _p("Curry", "9120035592385")])
    assert [p.ean for p in ps] == [None, None, "9120035592385", "9120035592385"] and "shared" in ps[0].extra["gtin_note"]
