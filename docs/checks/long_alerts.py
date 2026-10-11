"""Підозріло довгі волонтерські тривоги і що відбувалося в офіційних даних під час них.
Запуск: python long_alerts.py official_data_en.csv volunteer_data_en.csv"""
import sys
import numpy as np
import pandas as pd
from common import EXCLUDE, KYIV, VAL_START, load

o, v = load(sys.argv[1]), load(sys.argv[2])
v = v[~v.region.isin(EXCLUDE)].copy()
v["dur_h"] = (v.finished_at - v.started_at).dt.total_seconds() / 3600
tr = v[(v.started_at >= pd.Timestamp("2025-12-01", tz=KYIV)) & (v.started_at < VAL_START)]
print("train duration quantiles (h):", tr.dur_h.quantile([.5, .9, .99, .995, .999]).round(2).to_dict())
for th in (3, 6, 12, 24):
    print(f"train alerts > {th}h:", (tr.dur_h > th).sum(), tr[tr.dur_h > th].region.value_counts().head(5).to_dict())
OFF_END = o.started_at.max()
lg = v[(v.dur_h > 6) & (v.started_at >= pd.Timestamp("2025-06-01", tz="UTC")) & (v.finished_at < OFF_END)]
lg = lg.sort_values("dur_h", ascending=False)
print(f"\nvolunteer alerts > 6h, 2025-06 .. {OFF_END:%Y-%m-%d} (official data end):")
for _, r in lg.iterrows():
    og = o[o.oblast == r.region]
    starts = ((og.started_at > r.started_at) & (og.started_at < r.finished_at)).sum()
    n = int(r.dur_h * 60); m = np.zeros(n, bool)
    for s, f in zip(og.started_at, og.finished_at):
        i = int((s - r.started_at).total_seconds() // 60); j = int((f - r.started_at).total_seconds() // 60)
        if j > 0 and i < n: m[max(i, 0):min(j, n)] = True
    print(f"{r.region:24s} {r.started_at:%Y-%m-%d %H:%M} {r.dur_h:6.1f}h naive={r.naive} | "
          f"official starts inside: {starts:3d} | official active share: {m.mean():.2f}")
