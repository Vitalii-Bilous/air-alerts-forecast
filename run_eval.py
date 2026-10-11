"""Каркас оцінки. За замовчуванням: лише validation (дані після VAL_END відкидаються ще до побудови сітки).
Запуск: python run_eval.py --data data/volunteer_data_en.csv
Фінальний test (один раз!): python run_eval.py --data ... --final-test"""
import argparse
import pathlib

import numpy as np
import pandas as pd

from alerts.baselines import BASELINES, REFERENCE
from alerts.models import MODELS
from alerts.config import GRID_START, HORIZONS, REGIONS, TEST_END, TRAIN_STARTS, VAL_END, VAL_START
from alerts.data import cut_events, load_events
from alerts.evaluate import metrics_table, run_period
from alerts.features import add_features
from alerts.grid import build_grid, long_alert_mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="results")
    ap.add_argument("--final-test", action="store_true")
    args = ap.parse_args()

    period_start, period_end, tag = (VAL_END, TEST_END, "test") if args.final_test else (VAL_START, VAL_END, "val")
    raw = load_events(args.data)
    events = cut_events(raw, period_end)          # «замок»: нічого після кінця періоду
    print(f"[{tag}] events used: {len(events)}, last start: {events.started_at.max()}, period {period_start} .. {period_end}")
    missing = sorted(set(REGIONS) - set(events.region))
    assert not missing, f"no events for {missing}"

    grid = build_grid(events, GRID_START, period_end, REGIONS)
    table = add_features(grid, events)
    assert table.t.max() < period_end

    out = pathlib.Path(args.out)
    out.mkdir(exist_ok=True)
    forecasters = BASELINES + MODELS
    models = [b.name for b in forecasters]
    all_metrics, all_preds, chosen = [], [], []
    for ts_name, ts in TRAIN_STARTS.items():
        for H in HORIZONS:
            pred = run_period(table, events, H, ts, period_start, period_end, forecasters, log=chosen)
            lm = long_alert_mask(pred, events, H, cutoff=period_end)   # лише для додаткової метрики
            m = metrics_table(pred, models, REFERENCE, lm, H)
            m.insert(0, "train_start", ts_name)
            all_metrics.append(m)
            pred = pred.assign(H=H, train_start=ts_name, long_alert=lm)
            all_preds.append(pred)
    metrics = pd.concat(all_metrics, ignore_index=True)
    preds = pd.concat(all_preds, ignore_index=True)
    metrics.to_csv(out / f"{tag}_metrics.csv", index=False)
    pd.DataFrame(chosen).to_csv(out / f"{tag}_chosen_params.csv", index=False)
    preds.to_csv(out / f"{tag}_predictions.csv.gz", index=False)

    # Регіональна таблиця (H=3, усі години)
    reg = []
    for (tsn, H, r), d in preds.groupby(["train_start", "H", "region"]):
        for mdl in models:
            reg.append(dict(train_start=tsn, H=H, region=r, model=mdl, n=len(d), base_rate=d.y.mean(),
                            brier=float(np.mean((d[f"p_{mdl}"] - d.y) ** 2))))
    pd.DataFrame(reg).to_csv(out / f"{tag}_region_metrics.csv", index=False)

    plot_calibration(preds, models, out / f"{tag}_calibration.png")
    show = metrics[(metrics.hours == "all_hours")]
    cols = ["train_start", "H", "group", "model", "n", "base_rate", "brier", "brier_lo", "brier_hi",
            "bss", "bss_lo", "bss_hi", "log_loss", "pr_auc", "ece"]
    with pd.option_context("display.width", 250, "display.max_rows", 500, "display.float_format", "{:.4f}".format):
        print(show[cols].to_string(index=False))
    print(f"\nsaved: {out}/{tag}_metrics.csv, {tag}_region_metrics.csv, {tag}_predictions.csv.gz, {tag}_calibration.png")


def plot_calibration(preds, models, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, H in zip(axes, sorted(preds.H.unique())):
        d = preds[preds.H == H]
        bins = np.linspace(0, 1, 11)
        for mdl in models:
            p = d[f"p_{mdl}"].to_numpy()
            b = np.clip(np.digitize(p, bins[1:-1]), 0, 9)
            g = pd.DataFrame({"b": b, "p": p, "y": d.y.to_numpy()}).groupby("b").agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
            g = g[g.n >= 30]
            ax.plot(g.p, g.y, marker="o", label=mdl)
        ax.plot([0, 1], [0, 1], "k--", lw=1)
        ax.set(title=f"H={H}h, train from 2025-12, all hours", xlabel="predicted", ylabel="observed")
        ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)


if __name__ == "__main__":
    main()
