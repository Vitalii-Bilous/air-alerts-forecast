"""Тести на коректність міток/ознак і на leakage.
Запуск: python -m pytest -q tests
Якщо задати ALERTS_CSV=шлях/до/volunteer_data_en.csv, тест ознак додатково проженеться на реальних даних."""
import os

import numpy as np
import pandas as pd
import pytest

from alerts import config
from alerts.baselines import BASELINES
from alerts.models import MODELS
from alerts.data import cut_events, load_events
from alerts.evaluate import fold_rows, make_folds, run_period
from alerts.features import FEATURES, add_features
from alerts.grid import build_grid, long_alert_mask

UTC = "UTC"
REGS = ["Kharkivska oblast", "Kyiv City", "Donetska oblast"]   # Донецька: виняток для довгих тривог


def ts(s):
    return pd.Timestamp(s, tz=UTC)


def synthetic_events(start="2026-01-01", days=150, seed=1):
    """Випадкові тривоги без перекриттів у межах регіону + кілька naive і кілька довгих (>6 год)."""
    rng = np.random.default_rng(seed)
    rows = []
    for i, r in enumerate(REGS):
        t = ts(start)
        end = t + pd.Timedelta(days=days)
        rate_h = [2.0, 8.0, 5.0][i]                       # середній інтервал між тривогами, год
        while t < end:
            t = t + pd.Timedelta(minutes=float(rng.exponential(rate_h * 60)) + 1)
            dur = pd.Timedelta(minutes=float(rng.uniform(3, 90)))
            naive = rng.random() < 0.06
            if rng.random() < 0.01:
                dur = pd.Timedelta(hours=float(rng.uniform(7, 60)))   # «завислий» відбій
            if naive:
                dur = pd.Timedelta(minutes=30)
            rows.append((r, t, t + dur, naive))
            t = t + dur
    return pd.DataFrame(rows, columns=["region", "started_at", "finished_at", "naive"])


def table_for(events, start, end):
    grid = build_grid(events, start, end, REGS)
    return add_features(grid, events)


def perturb_after(events, t0, seed=2):
    """«Зіпсуй майбутнє»: усе, що стартувало >= t0, замінюємо випадковими тривогами;
    тривогам, що стартували до t0, але не мали відомого кінця до t0, даємо випадковий кінець після t0."""
    rng = np.random.default_rng(seed)
    past = events[events.started_at < t0].copy()
    # кінець невідомий у t0: звичайна тривога з finished_at > t0, або naive-тривога, після якої
    # до t0 ще не було нового старту (до нього в реальному часі вона виглядає незакритою)
    is_last = past.groupby("region").started_at.transform("max") == past.started_at
    unknown_end = (~past.naive & (past.finished_at > t0)) | (past.naive & is_last)
    n = int(unknown_end.sum())
    past.loc[unknown_end, "finished_at"] = t0 + pd.to_timedelta(rng.uniform(0.01, 80, n), unit="h")
    past.loc[unknown_end, "naive"] = rng.random(n) < 0.5
    fake = []
    for r in events.region.unique():
        t = t0
        for _ in range(300):
            t = t + pd.Timedelta(minutes=float(rng.exponential(120)) + 1)
            d = pd.Timedelta(minutes=float(rng.uniform(1, 600)))
            fake.append((r, t, t + d, bool(rng.random() < 0.3)))
            t = t + d
    fake = pd.DataFrame(fake, columns=events.columns)
    return pd.concat([past, fake]).sort_values(["region", "started_at"]).reset_index(drop=True)


# ---------- 1. коректність міток і ознак на ручному прикладі ----------

def test_labels_and_features_by_hand():
    ev = pd.DataFrame([
        ("Kyiv City", ts("2026-01-10 10:30"), ts("2026-01-10 11:10"), False),
        ("Kyiv City", ts("2026-01-10 15:20"), ts("2026-01-10 15:50"), True),   # naive: кінця не було
    ], columns=["region", "started_at", "finished_at", "naive"])
    g = add_features(build_grid(ev, ts("2026-01-10 00:00"), ts("2026-01-11 00:00"), ["Kyiv City"]), ev)
    row = g.set_index("t")
    assert row.loc[ts("2026-01-10 10:00"), "y1"] == 1 and row.loc[ts("2026-01-10 09:00"), "y1"] == 0
    assert row.loc[ts("2026-01-10 08:00"), "y3"] == 1 and row.loc[ts("2026-01-10 07:00"), "y3"] == 0
    assert row.loc[ts("2026-01-10 11:00"), "active_now"] == 1
    assert row.loc[ts("2026-01-10 11:00"), "minutes_since_start"] == 30
    assert row.loc[ts("2026-01-10 12:00"), "active_now"] == 0           # відбій о 11:10 уже був
    assert row.loc[ts("2026-01-10 10:00"), "active_now"] == 0           # старт о 10:30 ще не настав
    assert row.loc[ts("2026-01-10 18:00"), "active_now"] == 1           # naive: відбою не було
    assert row.loc[ts("2026-01-10 12:00"), "starts_last_3h"] == 1
    assert row.loc[ts("2026-01-10 14:00"), "starts_last_3h"] == 0
    # година доби за Києвом (січень: UTC+2)
    assert row.loc[ts("2026-01-10 10:00"), "hour_kyiv"] == 12


# ---------- 2. «Зіпсуй майбутнє»: ознаки для будь-якого t0 ----------

@pytest.mark.parametrize("t0", ["2026-01-20 05:00", "2026-02-14 17:37", "2026-03-30 23:59", "2026-05-01 00:00"])
def test_features_unchanged_when_future_perturbed(t0):
    t0 = ts(t0)
    ev = synthetic_events()
    a = table_for(ev, ts("2026-01-01"), ts("2026-06-01"))
    b = table_for(perturb_after(ev, t0), ts("2026-01-01"), ts("2026-06-01"))
    m = a.t <= t0
    pd.testing.assert_frame_equal(a.loc[m, ["region", "t"] + FEATURES].reset_index(drop=True),
                                  b.loc[m, ["region", "t"] + FEATURES].reset_index(drop=True))
    # контроль, що тест взагалі здатен щось помітити: після t0 ознаки мають змінитися
    assert not a.loc[~m, FEATURES].reset_index(drop=True).equals(b.loc[~m, FEATURES].reset_index(drop=True))


@pytest.mark.skipif(not os.environ.get("ALERTS_CSV"), reason="ALERTS_CSV не задано")
def test_features_unchanged_on_real_data():
    raw = cut_events(load_events(os.environ["ALERTS_CSV"]), config.VAL_END)
    ev = raw[raw.region.isin(config.REGIONS[::4])]
    regs = sorted(ev.region.unique())
    start, end = config.kyiv("2025-10-01"), config.VAL_END
    for t0 in [config.kyiv("2026-01-15") + pd.Timedelta(minutes=17), config.VAL_START - pd.Timedelta(hours=2)]:
        a = add_features(build_grid(ev, start, end, regs), ev)
        p = perturb_after(ev, t0)
        b = add_features(build_grid(p, start, end, regs), p)
        m = a.t <= t0
        pd.testing.assert_frame_equal(a.loc[m, FEATURES].reset_index(drop=True), b.loc[m, FEATURES].reset_index(drop=True))


# ---------- 3. «Зіпсуй майбутнє»: прогнози, t0 лише після межі навчання фолду ----------

@pytest.mark.parametrize("H", config.HORIZONS)
def test_predictions_unchanged_when_future_perturbed(H):
    ev = synthetic_events()
    p_start, p_end = ts("2026-04-01"), ts("2026-04-29")
    rng = np.random.default_rng(H)
    for fs, fe in make_folds(p_start, p_end):
        t0 = fs + pd.Timedelta(minutes=int(rng.integers(0, int((fe - fs).total_seconds() // 60))))
        outs = []
        for e in (ev, perturb_after(ev, t0, seed=H)):
            tab = table_for(e, ts("2026-01-01"), p_end)
            outs.append(run_period(tab, e, H, ts("2026-01-15"), fs, fe, BASELINES + MODELS))
        a, b = outs
        m = a.t <= t0
        cols = [f"p_{c.name}" for c in BASELINES + MODELS]
        assert m.any()
        pd.testing.assert_frame_equal(a.loc[m, cols].reset_index(drop=True), b.loc[m, cols].reset_index(drop=True))


# ---------- 4. межі фолдів і purge ----------

@pytest.mark.parametrize("H", config.HORIZONS)
def test_fold_boundaries_and_purge(H):
    ev = synthetic_events()
    p_start, p_end = ts("2026-04-01"), ts("2026-04-29")
    tab = table_for(ev, ts("2026-01-01"), p_end)
    h = pd.Timedelta(hours=H)
    folds = make_folds(p_start, p_end)
    assert len(folds) == 4
    for fs, fe in folds:
        tr, evr = fold_rows(tab, ev, H, ts("2026-01-15"), fs, fe, p_end)
        assert tr.t.max() + h <= fs                       # мітки train не заходять у фолд
        assert evr.t.min() >= fs and evr.t.max() < fe
        assert evr.t.max() + h <= p_end                   # purge на кінці періоду
        # старти, від яких залежать мітки train, усі < fs
        assert ev[(ev.started_at >= tr.t.min()) & (ev.started_at < tr.t.max() + h)].started_at.max() < fs


def test_long_alert_mask_uses_only_info_known_at_cutoff():
    ev = pd.DataFrame([
        ("Kyiv City", ts("2026-01-10 00:00"), ts("2026-01-12 00:00"), False),     # 48 год
        ("Donetska oblast", ts("2026-01-10 00:00"), ts("2026-01-12 00:00"), False),  # виняток
    ], columns=["region", "started_at", "finished_at", "naive"])
    g = build_grid(ev, ts("2026-01-09"), ts("2026-01-13"), ["Kyiv City", "Donetska oblast"])
    early = long_alert_mask(g, ev, 3, cutoff=ts("2026-01-10 04:00"))   # тривала лише 4 год -> ще не «довга»
    late = long_alert_mask(g, ev, 3, cutoff=ts("2026-01-13"))
    assert not early.any()
    assert late[(g.region == "Kyiv City").to_numpy()].sum() == 48 + 2   # [t, t+3) перетинає 48 год
    assert not late[(g.region == "Donetska oblast").to_numpy()].any()


# ---------- 5. «замок» на test ----------

def test_cut_events_locks_future():
    ev = synthetic_events(start="2026-08-01", days=80)
    cut = cut_events(ev, config.VAL_END)
    assert cut.started_at.max() < config.VAL_END
    assert (cut.finished_at.dropna() < config.VAL_END).all()
    assert len(cut) < len(ev)
