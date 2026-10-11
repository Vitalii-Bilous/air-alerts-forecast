"""Зведення test: hgb проти clim_7d і logreg (з ДІ), по тижнях і по регіонах.
Лише читає results/test_predictions.csv.gz; нічого не перенавчає.
Запуск: python analysis/summarize_test.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pandas as pd
from alerts.config import GRID_START, REGIONS, TEST_END
from alerts.data import cut_events, load_events
from alerts.evaluate import day_block_bootstrap
from alerts.features import add_features
from alerts.grid import build_grid

p = pd.read_csv("results/test_predictions.csv.gz", parse_dates=["t"])
p["week"] = (p.t - p.t.min()).dt.days // 7


def bss(d, m, ref):
    b, r = ((d[f"p_{m}"] - d.y) ** 2).mean(), ((d[f"p_{ref}"] - d.y) ** 2).mean()
    _, ci = day_block_bootstrap(d, f"p_{m}", f"p_{ref}")
    return f"{1 - b / r:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]"


print("== hgb проти суперників, усі години ==")
for H in (1, 3):
    d = p[p.H == H]
    for ref in ("clim_28d", "clim_7d", "logreg"):
        print(f"H={H} hgb vs {ref:9s} {bss(d, 'hgb', ref)}")
print("\n== по тижнях, H=3 ==")
for w, d in p[p.H == 3].groupby("week"):
    print(f"week {w} {d.t.min():%m-%d} base={d.y.mean():.3f}  vs clim_28d {bss(d, 'hgb', 'clim_28d')}  vs clim_7d {bss(d, 'hgb', 'clim_7d')}")
print("\n== ситуації (ознаки станом на t, без перенавчання) ==")
ev = cut_events(load_events("data/volunteer_data_en.csv"), TEST_END)
feats = add_features(build_grid(ev, GRID_START, TEST_END, REGIONS), ev)[["region", "t", "active_now", "starts_last_24h"]]
for H in (1, 3):
    d = p[p.H == H].merge(feats, on=["region", "t"], validate="1:1")
    for name, m in [("тривога активна в t", d.active_now == 1), ("тихо в t", d.active_now == 0),
                    ("за 24 год не було стартів", d.starts_last_24h == 0)]:
        print(f"H={H} {name}: share={m.mean():.2f} base={d[m].y.mean():.3f}"
              f"  vs clim_28d {bss(d[m], 'hgb', 'clim_28d')}  vs clim_7d {bss(d[m], 'hgb', 'clim_7d')}")
print("\n== регіони, H=3, BSS hgb проти clim_7d ==")
d = p[p.H == 3]
r = d.groupby("region").apply(lambda g: pd.Series(dict(
    base=g.y.mean(), bss_vs_7d=1 - ((g.p_hgb - g.y) ** 2).mean() / ((g.p_clim_7d - g.y) ** 2).mean())), include_groups=False)
print(r.sort_values("bss_vs_7d").round(3).to_string())
