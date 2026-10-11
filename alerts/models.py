"""Логістична регресія і бустинг з тим самим інтерфейсом, що й базові прогнозисти.

Підбір гіперпараметрів і ваги свіжих даних — лише на внутрішньому часовому спліті train фолду:
  inner_train: t + H <= cut,  inner_val: t >= cut,  де cut = (останній t у train + 1 год) - INNER_VAL_DAYS.
Критерій вибору — Brier на inner_val. Після вибору модель перенавчається на всьому train фолду."""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import (HGB_GRID, HGB_MAX_ITER, INNER_VAL_DAYS, LR_C_GRID, REGIONS, SEED,
                     WEIGHT_HALF_LIVES_DAYS)
from .features import FEATURES, NATIONAL_FEATURES

CYCLIC = ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]
NUMERIC = [f for f in FEATURES if f not in ("hour_kyiv", "dow_kyiv")] + CYCLIC
REGION_CODE = {r: i for i, r in enumerate(REGIONS)}


def _prep(df):
    X = df[[f for f in FEATURES if f in df.columns]].copy()
    X["hour_sin"] = np.sin(2 * np.pi * df.hour_kyiv / 24)
    X["hour_cos"] = np.cos(2 * np.pi * df.hour_kyiv / 24)
    X["dow_sin"] = np.sin(2 * np.pi * df.dow_kyiv / 7)
    X["dow_cos"] = np.cos(2 * np.pi * df.dow_kyiv / 7)
    X["region"] = df.region.map(REGION_CODE).astype(int)
    return X


def _weights(t, ref, half_life_days):
    if half_life_days is None:
        return None
    age_days = (ref - t).dt.total_seconds().to_numpy() / 86400
    return 0.5 ** (age_days / half_life_days)


def _brier(y, p):
    return float(np.mean((p - y) ** 2))


class _TunedModel:
    name = "model"
    drop = ()   # ознаки, які ця модель не використовує (для ablation)

    def __init__(self, H):
        self.H = H
        self.y = f"y{H}"

    # --- реалізується в нащадках ---
    def _grid(self):
        raise NotImplementedError

    def _make(self, params):
        raise NotImplementedError

    def _fit_one(self, params, X, y, w, X_val=None, y_val=None):
        m = self._make(params)
        kw = {}
        if w is not None:
            kw[self._weight_kw] = w
        m.fit(X, y, **kw)
        return m

    # --- спільна логіка ---
    def fit(self, train):
        train = train.sort_values("t")
        last_t = train.t.max()
        cut = last_t + pd.Timedelta(hours=1) - pd.Timedelta(days=INNER_VAL_DAYS)
        h = pd.Timedelta(hours=self.H)
        itr = train[train.t + h <= cut]
        iva = train[train.t >= cut]
        Xi, yi, Xv, yv = _prep(itr), itr[self.y].to_numpy(), _prep(iva), iva[self.y].to_numpy()
        best = None
        for hl in WEIGHT_HALF_LIVES_DAYS:
            w = _weights(itr.t, cut, hl)
            for params in self._grid():
                m = self._fit_one(params, Xi, yi, w, Xv, yv)
                score = _brier(yv, m.predict_proba(Xv)[:, 1])
                if best is None or score < best[0]:
                    best = (score, hl, params, m)
        self.inner_brier, self.half_life, self.params = best[0], best[1], dict(best[2])
        self._finalize_params(best[3])
        w = _weights(train.t, last_t + pd.Timedelta(hours=1), self.half_life)
        self.model = self._fit_one(self.params, _prep(train), train[self.y].to_numpy(), w)
        return self

    def _finalize_params(self, inner_model):
        pass

    def predict(self, df):
        return self.model.predict_proba(_prep(df))[:, 1]

    def describe(self):
        return dict(half_life=self.half_life, inner_brier=self.inner_brier, **self.params)


class LogReg(_TunedModel):
    name = "logreg"
    _weight_kw = "lr__sample_weight"

    def _grid(self):
        return [dict(C=c) for c in LR_C_GRID]

    def _make(self, params):
        pre = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
             [c for c in NUMERIC if c not in self.drop]),
            ("reg", OneHotEncoder(categories=[list(range(len(REGIONS)))], handle_unknown="ignore"), ["region"]),
        ])
        return Pipeline([("pre", pre), ("lr", LogisticRegression(C=params["C"], max_iter=2000))])


class HGB(_TunedModel):
    name = "hgb"
    _weight_kw = "sample_weight"

    def _grid(self):
        return list(HGB_GRID)

    def _cols(self):
        return [c for c in NUMERIC if c not in self.drop] + ["region"]

    def _make(self, params):
        p = {k: v for k, v in params.items() if k != "max_iter"}
        cat = [c == "region" for c in self._cols()]
        if "max_iter" in params:   # фінальне навчання: кількість ітерацій, знайдена early stopping
            return HistGradientBoostingClassifier(max_iter=params["max_iter"], early_stopping=False,
                                                  categorical_features=cat, random_state=SEED, **p)
        return HistGradientBoostingClassifier(max_iter=HGB_MAX_ITER, early_stopping=True, n_iter_no_change=20,
                                              categorical_features=cat, random_state=SEED, **p)

    def _fit_one(self, params, X, y, w, X_val=None, y_val=None):
        m = self._make(params)
        kw = {} if w is None else {"sample_weight": w}
        X = X[self._cols()]
        if "max_iter" not in params:
            # early stopping на ЧАСОВІЙ відкладеній вибірці (inner_val), а не на випадковій частині train
            m.fit(X, y, X_val=X_val[self._cols()], y_val=y_val, **kw)
        else:
            m.fit(X, y, **kw)
        m._cols = self._cols()
        return _ColWrap(m)

    def _finalize_params(self, inner_model):
        self.params["max_iter"] = int(inner_model.m.n_iter_)


class _ColWrap:
    """Обгортка, щоб predict_proba брав потрібні колонки."""

    def __init__(self, m):
        self.m = m

    def predict_proba(self, X):
        return self.m.predict_proba(X[self.m._cols])


class HGBNoNational(HGB):
    """Ablation: бустинг без ознак «по країні / по групі»."""
    name = "hgb_no_national"
    drop = tuple(NATIONAL_FEATURES)


MODELS = [LogReg, HGB]
