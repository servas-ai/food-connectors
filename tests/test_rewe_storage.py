from food_connectors.adapters.rewe import storage_info, Billa

def test_storage_frozen_from_badge_and_category():
    d = {"badges": ["pp-veget", "tiefkuehlung"], "parentCategories": [[{"name": "Tiefkühl"}, {"name": "Backwaren"}, {"name": "Süßes"}]],
         "storageAndUsageStatements": "entweder sofort zubereiten oder bei -18°C mindestens haltbar"}
    s = storage_info(d)
    assert s["storage"] == "frozen" and s["category_path"] == "Tiefkühl > Backwaren > Süßes"

def test_storage_chilled_and_unknown():
    assert storage_info({"parentCategories": [[{"name": "Kühlregal"}, {"name": "Menüschalen"}]]})["storage"] == "chilled"
    assert storage_info({"parentCategories": [[{"name": "Vorratsschrank"}]]})["storage"] is None

def test_listing_keeps_standard_price_next_to_promo():
    r = {"name": "Iglo Mohnnudeln", "sku": "00-3046", "slug": "iglo-mohnnudeln-003046", "amount": 500, "volumeLabelShort": "g", "inPromotion": True,
         "price": {"regular": {"value": 352, "perStandardizedQuantity": 704, "promotionText": "Bei 3 Packungen je"}, "standard": {"value": 529}, "baseUnitShort": "kg"}}
    p = Billa()._p(r)
    assert p.price_eur == 3.52 and p.extra["price_standard_eur"] == 5.29 and p.extra["in_promotion"] and p.extra["promotion_text"]
