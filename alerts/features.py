"""Ознаки станом на момент t. Кожна ознака використовує лише:
  * старти з started_at < t;
  * кінець тривоги лише як факт «уже закінчилась до t» (finished_at <= t);
  * мітки y_H(t') лише для t' + H <= t (тобто вже відомі в момент t).
Тривога з naive=True ніколи не мала повідомлення про відбій, тому в реальному часі вона виглядає
активною до наступного старту в цьому регіоні (вигаданий кінець +30 хв не використовуємо)."""
import numpy as np
import pandas as pd

from .config import (COUNT_WINDOWS_H, HORIZONS, HOUR_RATE_PSEUDOCOUNT, MAX_HOURS_SINCE_LAST_START,
                     MAX_MINUTES_SINCE_START, RATE_DAYS, RATE_DAYS_SHORT)

FEATURES = (["active_now", "minutes_since_start", "hours_since_last_start", "hour_kyiv", "dow_kyiv"]
            + [f"starts_last_{w}h" for w in COUNT_WINDOWS_H]
            + [f"rate28_{H}" for H in HORIZONS] + [f"rate7_{H}" for H in HORIZONS]
            + [f"rate28h_{H}" for H in HORIZONS])
# Ознаки «по країні» і «по групі»: сума регіональних ознак по всіх регіонах сітки (або групи) в той самий t
NATIONAL_FEATURES = (["nat_active_now"] + [f"nat_starts_last_{w}h" for w in (1, 3, 24)]
                     + ["grp_active_now"] + [f"grp_starts_last_{w}h" for w in (1, 3)])
FEATURES = FEATURES + NATIONAL_FEATURES


def add_features(grid, events, horizons=HORIZONS):
    """grid має бути відсортований за (region, t) і бути неперервним погодинно в кожному регіоні."""
    out = grid.copy()
    cols = {c: np.zeros(len(out)) for c in ["active_now", "minutes_since_start", "hours_since_last_start"]
            + [f"starts_last_{w}h" for w in COUNT_WINDOWS_H]}
    for region, idx in out.groupby("region", sort=False).indices.items():
        e = events[events.region == region]
        s = e.started_at.values
        # відомий кінець: NaT, якщо naive або кінець ще не настав (NaT після cut_events)
        known_end = np.where(e.naive.values, np.datetime64("NaT", "ns"), e.finished_at.values).astype("datetime64[ns]")
        t = out.t.values[idx].astype("datetime64[ns]")
        n_before = np.searchsorted(s, t, "left")            # кількість стартів < t
        has = n_before > 0
        last = np.clip(n_before - 1, 0, None)
        if len(s):
            last_start = s[last].astype("datetime64[ns]")
            end_last = known_end[last]
            not_ended = np.isnat(end_last) | (end_last > t)
        else:
            last_start = t
            not_ended = np.zeros(len(t), bool)
        active = has & not_ended
        since_start_min = (t - last_start) / np.timedelta64(1, "m")
        cols["active_now"][idx] = active
        cols["minutes_since_start"][idx] = np.where(active, np.minimum(since_start_min, MAX_MINUTES_SINCE_START), 0)
        cols["hours_since_last_start"][idx] = np.where(
            has, np.minimum(since_start_min / 60, MAX_HOURS_SINCE_LAST_START), MAX_HOURS_SINCE_LAST_START)
        for w in COUNT_WINDOWS_H:
            cols[f"starts_last_{w}h"][idx] = n_before - np.searchsorted(s, t - np.timedelta64(w, "h"), "left")
    for c, v in cols.items():
        out[c] = v
    # агрегати по країні / групі в той самий момент t (кожна складова вже «станом на t»)
    nat = out.groupby("t")[["active_now", "starts_last_1h", "starts_last_3h", "starts_last_24h"]].transform("sum")
    out["nat_active_now"] = nat["active_now"]
    for w in (1, 3, 24):
        out[f"nat_starts_last_{w}h"] = nat[f"starts_last_{w}h"]
    grp = out.groupby(["t", "group"])[["active_now", "starts_last_1h", "starts_last_3h"]].transform("sum")
    out["grp_active_now"] = grp["active_now"]
    for w in (1, 3):
        out[f"grp_starts_last_{w}h"] = grp[f"starts_last_{w}h"]

    # Частоти з уже відомих міток (покладаємось на неперервну погодинну сітку в регіоні)
    win = RATE_DAYS * 24
    for H in horizons:
        y = out.groupby("region", sort=False)[f"y{H}"]
        # rate28: середнє y(t') для t' у [t - 28 діб, t - H]
        out[f"rate28_{H}"] = y.transform(
            lambda x: x.shift(H).rolling(win - H + 1, min_periods=7 * 24).mean())
        # rate7: те саме за 7 діб
        win7 = RATE_DAYS_SHORT * 24
        out[f"rate7_{H}"] = y.transform(
            lambda x: x.shift(H).rolling(win7 - H + 1, min_periods=2 * 24).mean())
        # rate28h: середнє y(t - 24k), k = 1..28 (та сама година доби; біля переходу на літній час зсув на 1 год),
        # згладжене до rate28 з псевдолічильником
        def same_hour(x):
            acc = pd.Series(0.0, index=x.index)
            cnt = pd.Series(0.0, index=x.index)
            for k in range(1, RATE_DAYS + 1):
                sh = x.shift(24 * k)
                acc += sh.fillna(0)
                cnt += sh.notna()
            return pd.DataFrame({"acc": acc, "cnt": cnt})
        parts = [same_hour(g) for _, g in y]
        sh = pd.concat(parts).reindex(out.index)
        m = HOUR_RATE_PSEUDOCOUNT
        base = out[f"rate28_{H}"]
        out[f"rate28h_{H}"] = (sh.acc + m * base) / (sh.cnt + m)
    return out
