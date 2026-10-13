from food_connectors.adapters import spar_shop as S

HIT = {"id": "7833700", "masterValues": {"product-number": "7833700", "ecr-brand": "BEN’s ORIGINAL", "short-description-2": "Express Risotto Hühnchen Pilze",
       "short-description-3": "250 G", "price": 2.99, "regular-price": 3.49, "best-price": 2.99, "price-per-unit": "11.96 €/kg", "is-on-promotion": "true",
       "code-internal": "8800344440833", "url": "/bens-original-express-risotto-huehnchen-pilze/p/7833700",
       "image-url": "https://cdn1.interspar.at/cachableservlets/articleImage.dam/at/7833700/dt_main.jpg",
       "category-names": "Produkte|Feinkost & Konserven|Fertiggerichte|Vorratsschrank"}}

def test_to_product():
    p = S.to_product(HIT)
    assert p.source == "spar-shop" and p.price_eur == 2.99 and p.size_g == 250 and p.unit_price_eur == 11.96 and p.unit == "kg"
    assert p.ean is None and p.extra["spar_code_internal"] == "8800344440833" and p.extra["regular_price_eur"] == 3.49 and p.extra["on_promotion"] is True
    assert p.source_url.endswith("/p/7833700") and S.is_ready_meal(p)

def test_article_exact(monkeypatch):
    monkeypatch.setattr(S, "_q", lambda q, n=3, page=1: {"hits": [HIT]})
    assert S.article("7833700").source_id == "7833700"
    assert S.article("999") is None

def test_size_kg():
    assert S._size("1 KG") == 1000 and S._size("2 Stk") is None
