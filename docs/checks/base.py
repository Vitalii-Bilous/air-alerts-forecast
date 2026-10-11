"""Базові частоти старту тривоги в [t, t+H) лише на train. Запуск: python base.py volunteer_data_en.csv"""
import sys
import numpy as np
import pandas as pd
from common import EXCLUDE, KYIV, VAL_START, LONG_ALERT_HOURS, LONG_ALERT_EXEMPT, group, load

v = load(sys.argv[1])
v = v[~v.region.isin(EXCLUDE)]
print("regions used:", v.region.nunique(), "| excluded:", EXCLUDE)


def rates(start, mask_long):
    t0 = pd.Timestamp(start, tz=KYIV).tz_convert("UTC")
    rows = []
    for H in (1, 3):
        # purge: беремо лише t, для яких t+H <= початок validation
        g = pd.date_range(t0, VAL_START - pd.Timedelta(hours=H), freq="h", inclusive="left").values
        for r, x in v.groupby("region"):
            x = x.sort_values("started_at")
            s, f = x.started_at.values, x.finished_at.values
            y = np.searchsorted(s, g + np.timedelta64(H, "h")) > np.searchsorted(s, g)
            keep = np.ones(len(g), bool)
            if mask_long and r not in LONG_ALERT_EXEMPT:
                # прибираємо t, у яких [t, t+H) перетинається з тривогою довшою за LONG_ALERT_HOURS
                lg = x[(x.finished_at - x.started_at) > pd.Timedelta(hours=LONG_ALERT_HOURS)]
                for a, b in zip(lg.started_at.values, lg.finished_at.values):
                    keep &= ~((g > a - np.timedelta64(H, "h")) & (g < b))
            rows.append(dict(region=r, group=group(r), H=H, p=y[keep].mean(), masked=1 - keep.mean()))
    return pd.DataFrame(rows)


pd.set_option("display.width", 200)
for start in ["2025-12-01", "2022-03-15"]:
    for mask_long in (False, True):
        d = rates(start, mask_long)
        print(f"\n=== train {start} .. 2026-08-15 (Kyiv), purge H, mask_long={mask_long} ===")
        print(d.pivot_table(index=["group", "region"], columns="H", values="p").round(2).to_string())
        print(d.groupby(["group", "H"])[["p", "masked"]].mean().round(3).to_string())
