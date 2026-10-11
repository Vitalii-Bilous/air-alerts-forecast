"""Погодинна сітка (регіон × t, UTC), мітки й маска довгих тривог.

Мітки й маска дивляться в майбутнє за визначенням і НЕ є ознаками."""
import numpy as np
import pandas as pd

from .config import GROUP, HORIZONS, KYIV, LONG_ALERT_EXEMPT, LONG_ALERT_HOURS


def build_grid(events, start, end, regions, horizons=HORIZONS):
    hours = pd.date_range(start, end, freq="h", inclusive="left")
    tv = hours.values
    parts = []
    for region in regions:
        s = events.loc[events.region == region, "started_at"].values
        df = pd.DataFrame({"region": region, "t": hours})
        for H in horizons:
            # y_H(t) = 1, якщо є старт у [t, t+H)
            df[f"y{H}"] = (np.searchsorted(s, tv + np.timedelta64(H, "h"), "left")
                           > np.searchsorted(s, tv, "left")).astype(np.int8)
        parts.append(df)
    grid = pd.concat(parts, ignore_index=True)
    grid["group"] = grid.region.map(GROUP)
    kt = grid.t.dt.tz_convert(KYIV)
    grid["hour_kyiv"] = kt.dt.hour.astype(np.int8)
    grid["dow_kyiv"] = kt.dt.dayofweek.astype(np.int8)
    grid["date_kyiv"] = kt.dt.strftime("%Y-%m-%d")
    return grid


def long_alert_mask(grid, events, H, cutoff):
    """True там, де [t, t+H) перетинається з тривогою, довшою за LONG_ALERT_HOURS,
    якщо судити лише з того, що було відомо в момент cutoff (тривалість, що ще триває, = cutoff - start)."""
    e = events[(events.started_at < cutoff) & ~events.region.isin(LONG_ALERT_EXEMPT)]
    # naive-тривога (відбою не було) виглядає закритою лише після наступного старту в регіоні;
    # якщо вона остання до cutoff, то станом на cutoff вона ще «триває»
    is_last = e.groupby("region").started_at.transform("max") == e.started_at
    known = e.finished_at.notna() & (e.finished_at <= cutoff) & ~(e.naive & is_last)
    end = e.finished_at.where(known, cutoff)
    long_ = (end - e.started_at) > pd.Timedelta(hours=LONG_ALERT_HOURS)
    e, end = e[long_], end[long_]
    mask = np.zeros(len(grid), bool)
    if len(e) == 0:
        return mask
    t = grid.t.values
    reg = grid.region.values
    h = np.timedelta64(H, "h")
    for r, s, f in zip(e.region.values, e.started_at.values, end.values):
        mask |= (reg == r) & (t > s - h) & (t < f)
    return mask
