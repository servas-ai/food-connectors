import pathlib, shutil, pytest
from food_connectors.adapters import nah_frisch as N
FX = pathlib.Path(__file__).parent / "fixtures"
HTML = (FX / "nahfrisch_angebote.html").read_text()

def test_parse_weeks_and_tiles():
    o = N.offers(HTML)
    assert len(o) == 36 and len({x["tile_url"] for x in o}) == 36
    k41 = [x for x in o if x["kw"] == 41]; k42 = [x for x in o if x["kw"] == 42]
    assert len(k41) == 22 and len(k42) == 14
    assert k41[0]["valid_from"] == "2026-10-07" and k41[0]["valid_to"] == "2026-10-13"
    assert k42[0]["valid_from"] == "2026-10-14" and k42[0]["valid_to"] == "2026-10-20"
    assert all(x["tile_url"].startswith("https://www.nahundfrisch.at/media/") for x in o)  # /images,/storage robots-disallowed: never used

def test_product_without_ocr():
    p = N.to_product(N.offers(HTML)[2], ocr=False)
    assert p.store == "Nah&Frisch" and p.source == "nah-frisch" and p.price_eur is None and p.extra["ocr"] is False
    assert p.image_url.endswith("ONLINE_KW4142_26_355x455px2.png") and p.extra["valid_to"] == "2026-10-13"

@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract not installed")
def test_ocr_tiles():
    r = N.ocr_tile((FX / "nahfrisch_tile_iglo.png").read_bytes())
    assert r["name_lines"][-2:] == ["iglo", "Pikante Knödel"] and r["price_eur"] == 3.99 and "350-400 g" in r["pack_text"]
    r = N.ocr_tile((FX / "nahfrisch_tile_knorr.png").read_bytes())
    assert r["price_eur"] == 1.39 and "Suppen" in r["name_lines"]
