import json, sys, time, re
sys.path.insert(0, '/workspace/food-connectors')
from food_connectors.nutri import compute_nutriscore, NUTRI_SOURCES
off = NUTRI_SOURCES['off-nutri']
d = json.load(open('scored.json'))
try: cache = json.load(open('nutri_off_cache.json'))
except Exception: cache = {}
def key(r): return r.get('url') or r.get('name')
out, agree = {}, [0, 0]
RED = re.compile(r'rind|schwein|faschiert|lamm|wild|hirsch|gulasch|bolognese|leberk', re.I)
for r in d:
    e = {}; ean = r.get('ean')
    if ean and ean not in cache:
        try: cache[ean] = off.by_ean(ean)
        except Exception as ex: cache[ean] = None
        time.sleep(0.7)
    o = cache.get(ean) if ean else None
    ns = '' if r.get('nutriscore_status') == 'berechnet' else (r.get('nutriscore') or '').upper()
    if o:
        if o.get('nova'): e['nova'] = o['nova']; e['nova_source'] = 'Open Food Facts'
        if o.get('additives') is not None and o.get('nova'): e['additives'] = o['additives']
        if o.get('ecoscore') and o['ecoscore'] in 'ABCDE': e['ecoscore'] = o['ecoscore']
        if o.get('ingredients_analysis'): e['ingredients_analysis'] = [t.split(':')[-1] for t in o['ingredients_analysis']]
        if o.get('nutriscore'): e.update(nutriscore=o['nutriscore'], nutriscore_status='offiziell', nutriscore_source='Open Food Facts')
    if 'nutriscore' not in e and ns in ('A','B','C','D','E'):
        e.update(nutriscore=ns, nutriscore_status='offiziell', nutriscore_source=r.get('nut_source') or 'Händler/OFF')
    c = compute_nutriscore(kcal=r.get('kcal_100'), sugar=r.get('sugar_100'), satfat=r.get('satfat_100'), salt=r.get('salt_100'),
        fiber=r.get('fiber_100'), protein=r.get('protein_100'), fvl_pct=(o or {}).get('fvl_pct'), red_meat=bool(RED.search(r.get('name') or '')))
    if c:
        e['nutriscore_computed'] = {k: c[k] for k in ('grade', 'score', 'assumptions')}
        if 'nutriscore' in e: agree[0] += e['nutriscore'] == c['grade']; agree[1] += 1
        else: e.update(nutriscore=c['grade'], nutriscore_status='berechnet', nutriscore_source='Nutri-Score 2023, lokal berechnet')
    if e: out[key(r)] = e
json.dump(cache, open('nutri_off_cache.json', 'w'), ensure_ascii=False)
n = len(d); cnt = lambda f: sum(1 for v in out.values() if f(v))
stats = {'products': n, 'nutriscore_any': cnt(lambda v: 'nutriscore' in v), 'nutriscore_official': cnt(lambda v: v.get('nutriscore_status') == 'offiziell'),
    'nutriscore_berechnet': cnt(lambda v: v.get('nutriscore_status') == 'berechnet'), 'nova': cnt(lambda v: 'nova' in v), 'additives': cnt(lambda v: 'additives' in v),
    'ecoscore': cnt(lambda v: 'ecoscore' in v), 'computed_vs_official_agreement': f'{agree[0]}/{agree[1]}'}
json.dump({'stats': stats, 'by_key': out}, open('nutri_enrich.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(stats))
