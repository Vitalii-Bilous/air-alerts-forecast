"""Чи збігаються волонтерські старти регіону з офіційними стартами в інших областях частіше, ніж випадково.
Null: ті самі старти, зсунуті на ±30/60/120 хв. Запуск: python cross_region.py official_data_en.csv volunteer_data_en.csv"""
import sys
import numpy as np
import pandas as pd
from common import load

o, v = load(sys.argv[1]), load(sys.argv[2])
TOL = np.timedelta64(180, "s")


def rate(s, t, shift=0):
    t = np.sort(t); s = s + np.timedelta64(shift, "m")
    if len(t) < 2 or len(s) == 0: return np.nan
    i = np.clip(np.searchsorted(t, s), 1, len(t) - 1)
    return (np.minimum(np.abs(t[i] - s), np.abs(t[i - 1] - s)) <= TOL).mean()


def between(df, a, b):
    return df[(df.started_at >= pd.Timestamp(a, tz="UTC")) & (df.started_at < pd.Timestamp(b, tz="UTC"))]


SRC = ["Volynska oblast", "Lvivska oblast", "Rivnenska oblast", "Zhytomyrska oblast"]  # останні два: контроль
TGT = ["Volynska oblast", "Lvivska oblast", "Chernihivska oblast", "Sumska oblast", "Odeska oblast"]
for a, b in [("2025-01-01", "2025-09-01"), ("2026-01-01", "2026-09-01")]:
    print(f"\n=== {a} .. {b}: share of volunteer starts within ±3 min of an official start (null in brackets) ===")
    vv, oo = between(v, a, b), between(o, a, b)
    for src in SRC:
        s = vv[vv.region == src].started_at.values
        cells = []
        for tg in TGT:
            t = oo[oo.oblast == tg].started_at.values
            null = np.nanmean([rate(s, t, k) for k in (-120, -60, -30, 30, 60, 120)])
            cells.append(f"{tg.split()[0][:8]} {rate(s, t):.2f} ({null:.2f})")
        print(f"{src:20s} n={len(s):4d} | " + " | ".join(cells))
# який саме район «копіює» зіпсований регіон
a, b = "2026-01-01", "2026-09-01"
vv, oo = between(v, a, b), between(o, a, b)
for src, tg in [("Volynska oblast", "Chernihivska oblast"), ("Lvivska oblast", "Odeska oblast")]:
    s = vv[vv.region == src].started_at.values
    og = oo[(oo.oblast == tg) & (oo.level == "raion")]
    res = sorted(((rate(s, g.started_at.values), r) for r, g in og.groupby("raion")), reverse=True)[:3]
    print(f"\n{src} 2026 best-matching raions in {tg}:", [(round(x, 2), r) for x, r in res])
