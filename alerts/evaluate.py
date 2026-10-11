"""Прогін із щотижневим перенавчанням (rolling origin) і метрики."""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from .config import BOOTSTRAP_REPS, CALIBRATION_BINS, FOLD_DAYS, PROB_CLIP, SEED
from .grid import long_alert_mask


def make_folds(period_start, period_end):
    starts = pd.date_range(period_start, period_end, freq=f"{FOLD_DAYS}D", inclusive="left")
    return [(fs, min(fs + pd.Timedelta(days=FOLD_DAYS), period_end)) for fs in starts]


def fold_rows(table, events, H, train_start, fold_start, fold_end, period_end):
    """Рядки для навчання і оцінки одного фолду.
    train: t >= train_start і t + H <= fold_start (purge), без рядків із довгими тривогами,
           визначеними лише за тим, що відомо на fold_start;
    eval:  t у [fold_start, fold_end) і t + H <= period_end (purge на межі періоду)."""
    h = pd.Timedelta(hours=H)
    tr = table[(table.t >= train_start) & (table.t + h <= fold_start)]
    tr = tr[~long_alert_mask(tr, events, H, cutoff=fold_start)]
    ev = table[(table.t >= fold_start) & (table.t < fold_end) & (table.t + h <= period_end)]
    return tr, ev


def run_period(table, events, H, train_start, period_start, period_end, forecasters, log=None):
    """Повертає рядки (region, t, y, p_<model>) для всього періоду.
    Якщо передано список log, у нього пишуться вибрані на внутрішньому спліті параметри моделей."""
    out = []
    for k, (fs, fe) in enumerate(make_folds(period_start, period_end)):
        tr, ev = fold_rows(table, events, H, train_start, fs, fe, period_end)
        res = ev[["region", "group", "t", "date_kyiv", f"y{H}"]].rename(columns={f"y{H}": "y"}).copy()
        res["fold"] = k
        features_only = ev.drop(columns=[c for c in ev.columns if c.startswith("y")])
        for cls in forecasters:
            f = cls(H).fit(tr)
            res[f"p_{cls.name}"] = f.predict(features_only)
            if log is not None and hasattr(f, "describe"):
                log.append(dict(H=H, fold=k, fold_start=fs, model=cls.name, n_train=len(tr), **f.describe()))
        out.append(res)
    return pd.concat(out, ignore_index=True)


# ---------- метрики ----------

def _clip(p):
    return np.clip(p, PROB_CLIP, 1 - PROB_CLIP)


def brier(y, p):
    return float(np.mean((p - y) ** 2))


def log_loss(y, p):
    p = _clip(p)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def ece(y, p, bins=CALIBRATION_BINS):
    edges = np.linspace(0, 1, bins + 1)
    b = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    tot = 0.0
    for i in range(bins):
        m = b == i
        if m.any():
            tot += m.sum() * abs(p[m].mean() - y[m].mean())
    return tot / len(y)


def day_block_bootstrap(df, model, ref, reps=BOOTSTRAP_REPS, seed=SEED):
    """95% інтервали для Brier і BSS: перевибірка діб (за Києвом) з поверненням."""
    se = (df[model] - df.y) ** 2
    se_ref = (df[ref] - df.y) ** 2
    d = pd.DataFrame({"day": df.date_kyiv, "se": se, "se_ref": se_ref}).groupby("day").agg(
        se=("se", "sum"), se_ref=("se_ref", "sum"), n=("se", "size"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(reps, len(d)))
    S, R, N = d.se.values[idx].sum(1), d.se_ref.values[idx].sum(1), d.n.values[idx].sum(1)
    b, s = S / N, 1 - S / R
    return np.percentile(b, [2.5, 97.5]), np.percentile(s, [2.5, 97.5])


def metrics_table(pred, models, ref, long_mask, H):
    rows = []
    for mask_name, keep in [("all_hours", np.ones(len(pred), bool)), ("no_long_alerts", ~long_mask)]:
        for grp in ["all", "front", "center", "west"]:
            m = keep & ((pred.group == grp).to_numpy() if grp != "all" else True)
            d = pred[m]
            if len(d) == 0:
                continue
            y = d.y.to_numpy(float)
            bref = brier(y, d[f"p_{ref}"].to_numpy())
            for model in models:
                p = d[f"p_{model}"].to_numpy(float)
                bs = brier(y, p)
                (b_lo, b_hi), (s_lo, s_hi) = day_block_bootstrap(d, f"p_{model}", f"p_{ref}")
                rows.append(dict(
                    H=H, hours=mask_name, group=grp, model=model, n=len(d), base_rate=y.mean(),
                    brier=bs, brier_lo=b_lo, brier_hi=b_hi,
                    bss=1 - bs / bref, bss_lo=s_lo, bss_hi=s_hi,
                    log_loss=log_loss(y, p),
                    pr_auc=average_precision_score(y, p) if 0 < y.sum() < len(y) else np.nan,
                    ece=ece(y, p)))
    return pd.DataFrame(rows)
