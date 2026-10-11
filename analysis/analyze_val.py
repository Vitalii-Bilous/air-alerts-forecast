"""Глибший аналіз validation (test не чіпає): ablation ознак по країні та зрізи помилок.
Запуск: python analysis/analyze_val.py --data data/volunteer_data_en.csv  (потрібен results/val_predictions.csv.gz)"""
import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from alerts.config import GRID_START, HORIZONS, REGIONS, TRAIN_STARTS, VAL_END, VAL_START  # noqa: E402
from alerts.data import cut_events, load_events  # noqa: E402
from alerts.evaluate import day_block_bootstrap, run_period  # noqa: E402
from alerts.features import add_features  # noqa: E402
from alerts.grid import build_grid  # noqa: E402
from alerts.models import HGBNoNational  # noqa: E402


def bss(d, m, ref):
    b = np.mean((d[m] - d.y) ** 2); r = np.mean((d[ref] - d.y) ** 2)
    _, (lo, hi) = day_block_bootstrap(d, m, ref)
    return f"{1 - b / r:+.3f} [{lo:+.3f}, {hi:+.3f}]"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--out", default="results")
    a = ap.parse_args()
    events = cut_events(load_events(a.data), VAL_END)
    table = add_features(build_grid(events, GRID_START, VAL_END, REGIONS), events)
    preds = pd.read_csv(pathlib.Path(a.out) / "val_predictions.csv.gz", parse_dates=["t"])
    feats = table[["region", "t", "active_now", "nat_starts_last_3h", "nat_active_now", "starts_last_24h"]]
    rows = []
    for H in HORIZONS:
        p = preds[preds.H == H].drop(columns=["H", "train_start"])
        abl = run_period(table, events, H, TRAIN_STARTS["2025-12"], VAL_START, VAL_END, [HGBNoNational])
        p = p.merge(abl[["region", "t", "p_hgb_no_national"]], on=["region", "t"]).merge(feats, on=["region", "t"])
        p.to_csv(pathlib.Path(a.out) / f"val_analysis_H{H}.csv.gz", index=False)
        print(f"\n===== H={H} =====")
        print("Ablation (BSS hgb vs hgb_no_national):", bss(p, "p_hgb", "p_hgb_no_national"))
        print("hgb_no_national vs clim_7d:", bss(p, "p_hgb_no_national", "p_clim_7d"))
        print("hgb vs clim_7d:", bss(p, "p_hgb", "p_clim_7d"))
        slices = {
            "fold 0 (08-15..08-22)": p.fold == 0, "fold 1": p.fold == 1, "fold 2": p.fold == 2, "fold 3 (09-05..09-12)": p.fold == 3,
            "alert active in region at t": p.active_now == 1, "region quiet at t": p.active_now == 0,
            "country quiet: 0 starts in last 3h": p.nat_starts_last_3h == 0,
            "country busy: >=5 starts in last 3h": p.nat_starts_last_3h >= 5,
            "region had 0 starts in last 24h": p.starts_last_24h == 0,
        }
        for name, m in slices.items():
            d = p[m]
            print(f"  {name:40s} n={len(d):6d} base={d.y.mean():.3f} | hgb vs clim_28d {bss(d, 'p_hgb', 'p_clim_28d')}"
                  f" | hgb vs clim_7d {bss(d, 'p_hgb', 'p_clim_7d')}")
        # по регіонах
        reg = []
        for r, d in p.groupby("region"):
            reg.append(dict(H=H, region=r, group=d.group.iloc[0], n=len(d), base=d.y.mean(),
                            brier_hgb=np.mean((d.p_hgb - d.y) ** 2), brier_7d=np.mean((d.p_clim_7d - d.y) ** 2),
                            brier_28d=np.mean((d.p_clim_28d - d.y) ** 2)))
        reg = pd.DataFrame(reg)
        reg["bss_vs_7d"] = 1 - reg.brier_hgb / reg.brier_7d
        reg["bss_vs_28d"] = 1 - reg.brier_hgb / reg.brier_28d
        rows.append(reg)
        print(reg.sort_values("bss_vs_7d")[["region", "group", "base", "bss_vs_7d", "bss_vs_28d"]].round(3).to_string(index=False))
    pd.concat(rows).to_csv(pathlib.Path(a.out) / "val_region_hgb.csv", index=False)


if __name__ == "__main__":
    main()
