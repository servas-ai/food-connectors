"""Nutri-Score 2023 (updated algorithm, Scientific Committee 2022/2023) for general foods.
Inputs per 100 g. fvl_pct = fruit/vegetables/legumes %, default 0 (conservative, flagged)."""
import bisect
def _pts(v, th): return bisect.bisect_left(th, v) if v is not None else 0  # strictly-greater thresholds
def _gt(v, th): return sum(1 for t in th if v is not None and v > t)
ENERGY_KJ = [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350]
SUGAR = [3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51]
SATFAT = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
SALT = [round(0.2 * i, 1) for i in range(1, 21)]
FIBER = [3.0, 4.1, 5.2, 6.3, 7.4]
PROTEIN = [2.4, 4.8, 7.2, 9.6, 12.0, 14.0, 17.0]
def _fvl(p): return 5 if p > 80 else 2 if p > 60 else 1 if p > 40 else 0
def compute_nutriscore(kcal=None, sugar=None, satfat=None, salt=None, fiber=None, protein=None, fvl_pct=None, kj=None, red_meat=False):
    if (kcal is None and kj is None) or sugar is None or satfat is None or salt is None:
        return None
    kj = kj if kj is not None else kcal * 4.184
    neg = {"energy": _gt(kj, ENERGY_KJ), "sugar": _gt(sugar, SUGAR), "satfat": _gt(satfat, SATFAT), "salt": _gt(salt, SALT)}
    N = sum(neg.values())
    pf = _gt(fiber or 0, FIBER); pp = _gt(protein or 0, PROTEIN); pv = _fvl(fvl_pct or 0)
    if red_meat: pp = min(pp, 2)
    P = pf + pv + (pp if N < 11 else 0)
    s = N - P
    grade = "A" if s <= 0 else "B" if s <= 2 else "C" if s <= 10 else "D" if s <= 18 else "E"
    return {"grade": grade, "score": s, "negative": neg, "positive": {"fiber": pf, "protein": pp if N < 11 else 0, "fvl": pv},
            "algorithm": "Nutri-Score 2023 (general foods)", "status": "berechnet",
            "assumptions": [] if fvl_pct is not None else ["fvl_pct unbekannt -> 0 angenommen (konservativ)"] + ([] if fiber is not None else ["fiber unbekannt -> 0"])}
