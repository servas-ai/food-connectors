"""Live smoke test of every connector -> status.json (run: python3 tests/live_status.py)."""
import json, time, datetime as dt
from food_connectors.adapters import ADAPTERS
res = {}
for k, a in ADAPTERS.items():
    if a.status == "catalog-only": res[k] = {"status": "catalog-only"}; continue
    t = time.time()
    try:
        n = len(a.fetch(limit=20) if k in ("prepmymeal", "livefresh", "gourmetfein") else a.search("gulasch" if k not in ("off",) else "gulasch", limit=20))
        res[k] = {"status": "pass" if n else "fail (0 results)", "n": n}
    except Exception as e:
        res[k] = {"status": "fail", "error": repr(e)[:120]}
    res[k]["sec"] = round(time.time() - t, 1); print(k, res[k], flush=True); time.sleep(1)
def chk(name, fn):
    try: r = fn(); res[name] = {"status": "pass" if r else "fail (empty)"}
    except Exception as e: res[name] = {"status": "fail", "error": repr(e)[:120]}
    print(name, res[name], flush=True)
from food_connectors.nutri import nutri_lookup
from food_connectors import company as C, datasets as D
for s in ("off-nutri", "usda-fdc", "ciqual"):
    chk("nutri:" + s, lambda s=s: nutri_lookup("3017620422003" if s == "off-nutri" else "chicken soup" if s == "usda-fdc" else "soupe", [s]))
chk("company:gleif", lambda: C.company("HOFER KG"))
chk("company:vies", lambda: C.vies_check("ATU33582005"))
chk("company:northdata", lambda: C.northdata_page("Hofer KG"))
for h in ("hf", "zenodo", "datagv", "kaggle"):
    chk("datasets:" + h, lambda h=h: D.search("food", [h], 3)["results"])
json.dump({"tested_at": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z", "results": res}, open("status.json", "w"), indent=1)
