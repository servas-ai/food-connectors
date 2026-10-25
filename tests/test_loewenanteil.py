import json, pathlib
from food_connectors.adapters import loewenanteil as L

FX = pathlib.Path(__file__).parent / "fixtures"
H = (FX / "loewenanteil_classic-bolognese.html").read_text()
SP = json.loads((FX / "loewenanteil_classic-bolognese.json").read_text())["product"]
SHOP = json.loads((FX / "loewenanteil_products.json").read_text())["products"]


def test_parse_nutrition_and_product():
    per100, pack, size = L.parse_nutrition(H)
    assert size == 570.0
    assert per100["kcal"] == 83.0 and per100["protein"] == 7.0 and per100["fat"] == 3.4
    assert per100["satfat"] == 1.2 and per100["carbs"] == 5.5 and per100["sugar"] == 3.1
    assert per100["fiber"] == 1.2 and per100["salt"] == 0.99
    assert pack["kcal"] == 473.0 and pack["protein"] == 40.0
    p = L.to_product(SP, H)
    assert p.source == "loewenanteil" and p.store == "Online: Löwenanteil" and p.brand == "Löwenanteil"
    assert p.name == "Classic Bolognese" and p.price_eur == 9.99 and p.size_g == 570.0
    assert p.unit_price_eur == round(9.99 / 570 * 1000, 2) and p.unit == "kg"
    assert p.nutrition_100g == per100 and p.ean == "4262398291255"  # Einzeln variant barcode (GS1-valid), was wrongly dropped before T1207
    assert p.image_url and ("cdn.shopify.com" in p.image_url or "loewenanteil.com/cdn" in p.image_url)
    assert p.extra["portions"] == 2
    assert L.is_ready_meal(p)
    # products.json list includes available; single-product .json endpoint often omits it
    shop_bolo = next(x for x in SHOP if x["handle"] == "classic-bolognese")
    p2 = L.to_product(shop_bolo, H)
    assert p2.extra["available"] is True


def test_is_meal_filters():
    bolo = next(p for p in SHOP if p["handle"] == "classic-bolognese")
    assert L.is_meal(bolo)
    pasta = next(p for p in SHOP if p["handle"] == "protein-pasta")
    assert not L.is_meal(pasta)
    bundle = next(p for p in SHOP if p["handle"] == "probierpaket")
    assert not L.is_meal(bundle)
    hoodie = next(p for p in SHOP if p["handle"] == "hoodie")
    assert not L.is_meal(hoodie)


def test_spaced_kj_kcal_format():
    # Linsen à la Provence publishes "357 kJ / 85 kcal" with spaces around /
    html = """<table><tbody><tr><td><strong>Nährwerte</strong></td><td><strong>pro 100 g</strong></td>
    <td><strong>pro Glas (570 g)</strong></td></tr>
    <tr><td>Brennwert</td><td>357 kJ / 85 kcal</td><td>2036 kJ / 485 kcal</td></tr>
    <tr><td>Fett<br>davon gesättigt</td><td>2,0 g<br>0,2 g</td><td>11 g<br>1,1 g</td></tr>
    <tr><td>Kohlenhydrate<br>davon Zucker**</td><td>10 g<br>2,4 g</td><td>57 g<br>14 g</td></tr>
    <tr><td>Ballaststoffe</td><td>3,1 g</td><td>18 g</td></tr>
    <tr><td>Eiweiß</td><td>5,2 g</td><td>30 g</td></tr>
    <tr><td>Salz</td><td>0,8 g</td><td>4,6 g</td></tr></tbody></table>"""
    per100, pack, size = L.parse_nutrition(html)
    assert size == 570.0 and per100["kcal"] == 85.0 and per100["protein"] == 5.2
    assert pack["kcal"] == 485.0 and per100["satfat"] == 0.2


def test_missing_html_keeps_nulls():
    p = L.to_product(SP, "")
    assert p.size_g is None and p.nutrition_100g == {} and not L.is_ready_meal(p)
