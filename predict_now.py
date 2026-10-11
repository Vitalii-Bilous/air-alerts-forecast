"""Прогноз «на зараз»: ймовірність старту тривоги в кожній з 21 області протягом наступних 1 і 3 год.

Модель (hgb) навчається з нуля на всіх даних з 2025-12-01, мітки яких уже відомі в момент прогнозу,
тим самим кодом, що й в оцінці (внутрішній спліт, маска довгих тривог станом на момент прогнозу).
Усі події після моменту прогнозу відкидаються ще до побудови сітки (cut_events), тож майбутнє не бачимо.

Запуск:
  python predict_now.py --data data/volunteer_data_en.csv                      # момент = година після останнього запису
  python predict_now.py --data data/volunteer_data_en.csv --at "2026-10-05 18:00"   # момент за київським часом
"""
import argparse

import pandas as pd

from alerts.baselines import Clim7d
from alerts.config import GRID_START, HORIZONS, KYIV, REGIONS, TRAIN_STARTS
from alerts.data import cut_events, load_events
from alerts.features import add_features
from alerts.grid import build_grid, long_alert_mask
from alerts.models import HGB


def forecast(raw, t):
    """Прогноз для всіх регіонів у момент t (UTC, ціла година). Повертає DataFrame."""
    events = cut_events(raw, t)                      # лише те, що було відомо в момент t
    table = add_features(build_grid(events, GRID_START, t + pd.Timedelta(hours=1), REGIONS), events)
    now = table[table.t == t]
    X = now.drop(columns=[c for c in now.columns if c.startswith("y")])
    out = now[["region", "group", "active_now"]].copy()
    for H in HORIZONS:
        tr = table[(table.t >= TRAIN_STARTS["2025-12"]) & (table.t + pd.Timedelta(hours=H) <= t)]
        tr = tr[~long_alert_mask(tr, events, H, cutoff=t)]
        out[f"p_{H}h"] = HGB(H).fit(tr).predict(X)
        out[f"clim7d_{H}h"] = Clim7d(H).fit(tr).predict(X)
    return out.reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--at", help="момент прогнозу за київським часом, напр. '2026-10-05 18:00'; округлюється вниз до години")
    ap.add_argument("--out", help="куди зберегти CSV (необов'язково)")
    a = ap.parse_args()

    raw = load_events(a.data)
    if a.at:
        t = pd.Timestamp(a.at, tz=KYIV).tz_convert("UTC").floor("h")
    else:
        last = pd.concat([raw.started_at, raw.finished_at]).max()
        t = last.floor("h") + pd.Timedelta(hours=1)
    print(f"Прогноз на {t.tz_convert(KYIV):%Y-%m-%d %H:%M} (Київ) = {t:%Y-%m-%d %H:%M} UTC; "
          f"використано події до цього моменту. Навчання ~1 хв...")
    res = forecast(raw, t)
    if a.out:
        res.to_csv(a.out, index=False)
    show = res.sort_values("p_3h", ascending=False)
    with pd.option_context("display.width", 200, "display.float_format", "{:.2f}".format):
        print(show.to_string(index=False))


if __name__ == "__main__":
    main()
