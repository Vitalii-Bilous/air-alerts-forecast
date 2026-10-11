"""Базові прогнозисти. Інтерфейс: fit(train_df) -> self, predict(df) -> np.ndarray ймовірностей.
train_df і df містять мітки й ознаки з alerts.features; predict не має права читати мітки df."""
import numpy as np


class Baseline:
    name = "base"

    def __init__(self, H):
        self.H = H
        self.y = f"y{H}"

    def fit(self, train):
        self.region_rate = train.groupby("region")[self.y].mean()
        self.global_rate = train[self.y].mean()
        return self

    def _region_fallback(self, df):
        return df.region.map(self.region_rate).fillna(self.global_rate).to_numpy(float)


class ClimTrain(Baseline):
    """Частка y=1 у регіоні за весь train фолду."""
    name = "clim_train"

    def predict(self, df):
        return self._region_fallback(df)


class Clim28d(Baseline):
    """Частка y=1 у регіоні за останні 28 діб до t (лише вже відомі мітки)."""
    name = "clim_28d"

    def predict(self, df):
        p = df[f"rate28_{self.H}"].to_numpy(float)
        return np.where(np.isnan(p), self._region_fallback(df), p)


class Clim7d(Baseline):
    """Частка y=1 у регіоні за останні 7 діб до t (коротше вікно, швидше реагує на дрейф, але шумніше)."""
    name = "clim_7d"

    def predict(self, df):
        p = df[f"rate7_{self.H}"].to_numpy(float)
        return np.where(np.isnan(p), self._region_fallback(df), p)


class Clim28dHour(Baseline):
    """Те саме для тієї ж години доби, згладжене до 28-денної частоти."""
    name = "clim_28d_hour"

    def predict(self, df):
        p = df[f"rate28h_{self.H}"].to_numpy(float)
        return np.where(np.isnan(p), self._region_fallback(df), p)


class RecentStart(Baseline):
    """Частка y=1 на train окремо для «був старт за останні H год» / «не був», по регіону."""
    name = "recent_start"

    def fit(self, train):
        super().fit(train)
        key = train[f"starts_last_{self.H}h"] > 0
        self.table = train.groupby([train.region, key])[self.y].mean()
        return self

    def predict(self, df):
        key = (df[f"starts_last_{self.H}h"] > 0).to_numpy()
        p = np.array([self.table.get((r, k), np.nan) for r, k in zip(df.region.to_numpy(), key)], float)
        return np.where(np.isnan(p), self._region_fallback(df), p)


BASELINES = [ClimTrain, Clim28d, Clim7d, Clim28dHour, RecentStart]
REFERENCE = "clim_28d"
