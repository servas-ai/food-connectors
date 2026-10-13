import json, os, pytest
from food_connectors.schema import parse_size_g, find_producer_id, looks_like_ready_meal, Product
from food_connectors.mcp_server import handle
from food_connectors.adapters import ADAPTERS
def test_size():
    assert parse_size_g("400 g") == 400 and parse_size_g("0,8 kg") == 800 and parse_size_g("2 x 150g") == 300
def test_id():
    assert find_producer_id("Hergestellt AT 40047 EG Wien") == "AT 40047 EG"
def test_meal():
    assert looks_like_ready_meal("Felix Chili con Carne") and not looks_like_ready_meal("Maggi Fix für Chili con Carne")
    assert not looks_like_ready_meal("Hühnerfaschiertes frisch")
def test_schema():
    d = Product(source="x", store="y", name="z").to_dict()
    for k in ("name", "brand", "store", "price_eur", "unit_price_eur", "size_g", "nutrition_100g", "ean", "image_url", "producer_id", "source_url", "fetched_at"): assert k in d
def test_mcp():
    assert handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})["result"]["serverInfo"]["name"] == "food-connectors"
    names = [t["name"] for t in handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
    assert "search_products" in names
    r = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "list_sources", "arguments": {}}})
    assert "gurkerl" in r["result"]["content"][0]["text"]
def test_registry():
    assert {"billa", "penny", "gurkerl", "lidl", "spar", "hofer", "dm", "mpreis", "unimarkt", "off", "heisse-preise"} <= set(ADAPTERS)
live = pytest.mark.skipif(not os.environ.get("LIVE"), reason="set LIVE=1 for network tests")
@live
def test_gurkerl_live():
    r = ADAPTERS["gurkerl"].search("chili con carne", 5); assert r
    p = ADAPTERS["gurkerl"].enrich(r[0]); assert p.nutrition_100g
@live
def test_lidl_live(): assert ADAPTERS["lidl"].search("gulasch", 5) is not None

def test_nutriscore_2023():
    from food_connectors.nutri import compute_nutriscore
    assert compute_nutriscore(kcal=60, sugar=1, satfat=0.3, salt=0.3, fiber=4, protein=5)["grade"] == "A"
    assert compute_nutriscore(kcal=500, sugar=40, satfat=12, salt=2, fiber=0, protein=5)["grade"] == "E"
    assert compute_nutriscore(kcal=None, sugar=1, satfat=1, salt=1) is None

def test_mealprep_nutrition_parser():
    from food_connectors.adapters.mealprep import parse_nutrition
    h = '<p>Nährwerte</p><table><tr><td>Nährwerte</td><td>Pro 100g</td><td>Portion (500g)</td></tr><tr><td>Energiegehalt</td><td>528kj/ 125kcal</td><td>625kcal</td></tr><tr><td>Fett</td><td>3,6g</td><td>18g</td></tr><tr><td>davon gesättigte Fettsäuren</td><td>1,2g</td><td>6g</td></tr><tr><td>Eiweiß</td><td>9g</td><td>45g</td></tr></table>'
    n, por = parse_nutrition(h)
    assert n == {"kcal": 125.0, "fat": 3.6, "satfat": 1.2, "protein": 9.0} and por == 500.0



def test_osm_stores_label_and_mcp():
    from food_connectors.adapters.osm_stores import _chain_label, CHAIN_PAT, REGIONS
    assert _chain_label({"brand": "Billa", "name": "Billa Linz"}) == "Billa"
    assert _chain_label({"name": "denn's BioMarkt"}) == "denn's BioMarkt"
    assert _chain_label({"brand": "Nah & Frisch"}) == "Nah&Frisch"
    assert "linz" in REGIONS and "billa" in CHAIN_PAT
    names = [t["name"] for t in handle({"jsonrpc": "2.0", "id": 9, "method": "tools/list"})["result"]["tools"]]
    assert "list_stores" in names
    # registry exposes catalog denns/nah-frisch
    assert "denns" in ADAPTERS and "nah-frisch" in ADAPTERS
    # unimarkt-shop: verified closed 2026-10-13 -> catalog-only, never returns fabricated products
    u = ADAPTERS["unimarkt-shop"]; assert u.status == "catalog-only" and "eingestellt" in u.notes
    assert u.search("gulasch") == [] and u.fetch() == []

def test_gurkerl_composition_parser():
    from food_connectors.adapters.gurkerl import parse_composition, MEAL_CATEGORIES
    c = {"productId": 49016, "nutritionalValues": [{"portion": "100 g", "values": {"energyKCal": {"amount": 127.0, "unit": "kCal"},
         "protein": {"amount": 8.0, "unit": "g"}, "salt": {"amount": 0.97, "unit": "g"}, "fiber": {"amount": None, "unit": "g"}}}],
         "plainIngredients": "Zutaten: Hähnchenfleisch 39 %\nHersteller: Perutnina Ptuj d.d.", "ean": "3838977051704"}
    n, ing, prod, pid, ean = parse_composition(c)
    assert n == {"kcal": 127.0, "protein": 8.0, "salt": 0.97} and ean == "3838977051704" and prod.startswith("Perutnina")
    assert parse_composition({"nutritionalValues": [], "plainIngredients": ""})[0] == {}
    assert 135049 in MEAL_CATEGORIES and 602 in MEAL_CATEGORIES
@live
def test_gurkerl_category_live():
    g = ADAPTERS["gurkerl"]; ids = g.category_ids(135049); assert len(ids) > 20
    ps = g.products(ids[:3]); assert ps and ps[0].price_eur and ps[0].image_url


def test_mpreis_shop_jsonld_fixture(monkeypatch):
    import pathlib
    from food_connectors.adapters import mpreis_shop as M
    html = (pathlib.Path(__file__).parent / "fixtures" / "mpreis_product.html").read_text()
    monkeypatch.setattr(M, "_html", lambda url: html)
    p = M.product("https://www.mpreis.at/shop/p/felix-erdaepfelgulasch-158321")
    assert p.brand == "Felix" and p.source_id == "158321" and p.ean == "9000295832943"
    assert p.size_g == 800 and p.price_eur > 0 and p.image_url.startswith("https://")
    assert p.nutrition_100g["kcal"] == 104 and p.nutrition_100g["salt"] == 1.2
    assert "Kartoffeln" in p.extra["ingredients"]
