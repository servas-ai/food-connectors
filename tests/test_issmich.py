"""Offline tests for the iss mich! (issmich.at, Shopware 6) adapter — trimmed real product pages + stored
tesseract output of the official Nährwerttabelle images (no network, no tesseract needed)."""
import json, pathlib
from food_connectors.adapters import issmich as I

FX = pathlib.Path(__file__).parent / "fixtures"
CHILI_URL = "https://www.issmich.at/Bio-Shop/Eintoepfe/Fleisch/16/Tex-Mex-Bio-Chili-con-Carne"
TAJINE_URL = "https://www.issmich.at/Bio-Shop/Eintoepfe/Fleisch/53/Marokkanische-Bio-Huehnertajine"


def test_parse_page_chili():
    d = I.parse_page((FX / "issmich_chili.html").read_text(), CHILI_URL)
    assert d["name"] == "Tex-Mex Bio Chili con Carne"
    assert d["price_eur"] == 10.3 and d["list_price_eur"] is None and d["deposit_eur"] == 2.0
    assert d["size_g"] == 280.0 and d["sku"] == "FL0002" and d["available"] is True
    assert d["gtin"] == "9120068110174" and I.gtin_ok(d["gtin"])
    assert d["images"] and "chili-con-carne" in d["images"][0] and "logo" not in d["images"][0]
    assert d["nutrition_image"] and "/NT_" in d["nutrition_image"].replace("%20", " ")
    assert d["ingredients"].startswith("Rinderbouillon") and d["allergens"] == "Sellerie"
    assert d["course"] == "Eintopf"


def test_sale_price_and_list_price():
    d = I.parse_page((FX / "issmich_tajine.html").read_text(), TAJINE_URL)
    assert d["price_eur"] == 8.0 and d["list_price_eur"] == 11.5


def test_ocr_solver_matches_printed_table():
    texts = json.loads((FX / "issmich_chili_ocr.json").read_text())["texts"]
    per100, perp = I.solve_ocr(texts, 280.0)
    assert per100 == {"fat": 7.3, "satfat": 2.4, "carbs": 5.8, "sugar": 1.3, "protein": 7.2, "salt": 0.31, "kcal": 120.7}
    assert perp["kcal"] == 338.0 and perp["protein"] == 20.2
    assert I.nutrition_problems(per100) == []


def test_candidates_g_read_as_9():
    assert I._cands("7,39")[0] == 7.3          # '7,3 g' with g→9
    assert I._cands("0,319", 2)[0] == 0.31     # salt '0,31 g'
    assert 7.3 in I._cands("739")              # comma lost
    assert I._cands("20,4")[0] == 20.4


def test_strict_gate_rejects_inconsistent_label():
    # Lammragout label: 0,9 g Eiweiß / 150,9 kcal per 100 g → Atwater mismatch → rejected, not invented
    bad = I.nutrition_problems({"kcal": 150.9, "fat": 8.0, "carbs": 3.4, "protein": 0.9, "salt": 0.32})
    assert bad and "Atwater" in bad[0]


def test_to_product_and_meal_filter():
    d = I.parse_page((FX / "issmich_chili.html").read_text(), CHILI_URL)
    texts = json.loads((FX / "issmich_chili_ocr.json").read_text())["texts"]
    a, b = I.solve_ocr(texts, 280.0)
    p = I.to_product(d, CHILI_URL, {"per100": a, "per_portion": b, "portion_g": 280.0, "ocr_ok": True, "problems": []})
    assert p.store == "Online: iss mich!" and p.ean == "9120068110174" and p.unit_price_eur == round(10.3 / 280 * 1000, 2)
    assert p.nutrition_100g["protein"] == 7.2 and p.extra["nut_ocr"] is True and I.is_ready_meal(p)
    d2 = dict(d, course="Beilage")
    assert not I.is_ready_meal(I.to_product(d2, CHILI_URL))
    assert not I.gtin_ok("9120068110175")
