"""MPreis product pages can show a portion block before the per-100 g block; only per-100 g may land in nutrition_100g."""
from food_connectors.adapters import mpreis_shop as M

LD = '<script type="application/ld+json">{"@type":"Product","name":"Bistro Avignon","sku":"1","gtin":"0400","brand":{"name":"Dr. Oetker"},"offers":{"price":"2.99","url":"https://www.mpreis.at/shop/p/x-1"}}</script>'
def block(title, kcal, prot):
    return (f'<div class="c3-detail-information__content-block-title">{title}</div><div><table><tbody>'
            f'<tr><td>Energie [kcal]</td><td class="c3-table__column-value">{kcal}</td></tr>'
            f'<tr><td>Eiweiß</td><td class="c3-table__column-value">{prot} g</td></tr></tbody></table></div>')

def _run(monkeypatch, body):
    monkeypatch.setattr(M, "_html", lambda url: LD + body)
    return M.product("https://www.mpreis.at/shop/p/x-1").nutrition_100g

def test_prefers_per100_over_portion(monkeypatch):
    body = ('<div class="c3-detail-information__content-block-title">Zutatenliste</div><div>WEIZENMEHL</div>'
            + block("Nicht zubereitete Portion (125 g)", 283, 11) + block("Nicht zubereitet je 100 g", 227, 8.9))
    assert _run(monkeypatch, body) == {"kcal": 227.0, "protein": 8.9}

def test_portion_only_left_empty(monkeypatch):
    assert _run(monkeypatch, block("Nicht zubereitete Portion (355 g)", 865, 36)) == {}

def test_single_per100_block(monkeypatch):
    assert _run(monkeypatch, block("Nicht zubereitet je 100 g", 427, 7)) == {"kcal": 427.0, "protein": 7.0}
