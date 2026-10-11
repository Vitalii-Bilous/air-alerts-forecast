"""Розбивка волонтерських стартів за серпень 2026 відносно офіційних у тій самій області.
Запуск: python breakdown.py official_data_en.csv volunteer_data_en.csv"""
import sys
import numpy as np
import pandas as pd
from common import load

o, v = load(sys.argv[1]), load(sys.argv[2])
a, b = pd.Timestamp("2026-08-01", tz="UTC"), pd.Timestamp("2026-09-01", tz="UTC")
# офіційні беремо з запасом 6 днів назад, щоб бачити тривоги, що почались до серпня і ще тривають
o = o[(o.started_at >= a - pd.Timedelta(days=6)) & (o.started_at < b)]
v = v[(v.started_at >= a) & (v.started_at < b) & ~v.region.isin(["Lvivska oblast", "Volynska oblast"])]
cats = ["<=3 min", "3-10 min", "10-30 min", "official already active", "no official"]
rows = []
for reg, g in v.groupby("region"):
    og = o[o.oblast == reg]
    os_, of = og.started_at.values, og.finished_at.values
    for s in g.started_at.values:
        d = np.min(np.abs(os_ - s)) if len(os_) else np.timedelta64(10**9, "s")
        if d <= np.timedelta64(3, "m"): c = cats[0]
        elif d <= np.timedelta64(10, "m"): c = cats[1]
        elif d <= np.timedelta64(30, "m"): c = cats[2]
        elif ((os_ < s) & (of > s)).any(): c = cats[3]
        else: c = cats[4]
        rows.append((reg, c))
r = pd.DataFrame(rows, columns=["region", "cat"])
print("volunteer starts:", len(r))
print(r.cat.value_counts(normalize=True).reindex(cats).round(3).to_string())
print("\nper region (share):")
print(pd.crosstab(r.region, r.cat, normalize="index").reindex(columns=cats).round(2).to_string())
