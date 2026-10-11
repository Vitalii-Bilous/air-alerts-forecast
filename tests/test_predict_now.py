"""predict_now: прогноз у момент t не змінюється, якщо зіпсувати все, що сталося після t.
Працює на реальних даних (~2 хв), тому запускається лише з ALERTS_CSV=шлях/до/volunteer_data_en.csv."""
import os

import numpy as np
import pandas as pd
import pytest

from alerts.data import load_events
from predict_now import forecast


@pytest.mark.skipif(not os.environ.get("ALERTS_CSV"), reason="ALERTS_CSV не задано")
def test_predict_now_ignores_future():
    raw = load_events(os.environ["ALERTS_CSV"])
    t = pd.Timestamp("2026-10-05 18:00", tz="Europe/Kyiv").tz_convert("UTC")
    a = forecast(raw, t)
    # майбутнє «псуємо»: старти після t видаляємо, кінці після t замінюємо випадковими
    rng = np.random.default_rng(1)
    bad = raw[raw.started_at < t].copy()
    m = bad.finished_at > t
    bad.loc[m, "finished_at"] = t + pd.to_timedelta(rng.integers(1, 600, m.sum()), "m")
    b = forecast(bad, t)
    assert len(a) == 21
    cols = [c for c in a.columns if c.startswith(("p_", "clim7d_"))] + ["active_now"]
    np.testing.assert_array_equal(a[cols].to_numpy(), b[cols].to_numpy())
