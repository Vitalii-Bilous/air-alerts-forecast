"""Усі зафіксовані рішення постановки (див. notes/step1*, step2_eval_design.md)."""
import pandas as pd

KYIV = "Europe/Kyiv"


def kyiv(date):
    """Північ за Києвом -> UTC Timestamp."""
    return pd.Timestamp(date, tz=KYIV).tz_convert("UTC")


# Регіони
EXCLUDE = ["Luhanska oblast", "Lvivska oblast", "Volynska oblast", "Zakarpatska oblast"]
FRONT = ["Chernihivska oblast", "Sumska oblast", "Kharkivska oblast", "Donetska oblast",
         "Zaporizka oblast", "Khersonska oblast", "Dnipropetrovska oblast", "Mykolaivska oblast"]
CENTER = ["Kyiv City", "Kyivska oblast", "Zhytomyrska oblast", "Vinnytska oblast",
          "Cherkaska oblast", "Poltavska oblast", "Kirovohradska oblast", "Odeska oblast"]
WEST = ["Rivnenska oblast", "Ternopilska oblast", "Khmelnytska oblast",
        "Ivano-Frankivska oblast", "Chernivetska oblast"]
REGIONS = FRONT + CENTER + WEST
GROUP = {**{r: "front" for r in FRONT}, **{r: "center" for r in CENTER}, **{r: "west" for r in WEST}}

# Горизонти, години
HORIZONS = (1, 3)

# Спліт (межі на 00:00 за Києвом)
GRID_START = kyiv("2022-03-01")
# Рішення після validation кроку 2: train з грудня 2025 (варіант «з 2022» був гіршим для clim_train)
TRAIN_STARTS = {"2025-12": kyiv("2025-12-01")}
VAL_START = kyiv("2026-08-15")
VAL_END = kyiv("2026-09-12")     # = початок test
TEST_END = kyiv("2026-10-10")
FOLD_DAYS = 7

# Довгі тривоги: > 6 год вважаємо пропущеним відбоєм, крім регіонів, де вони справжні
LONG_ALERT_HOURS = 6
LONG_ALERT_EXEMPT = ["Donetska oblast", "Zaporizka oblast"]

# Ознаки
MAX_MINUTES_SINCE_START = 6 * 60
MAX_HOURS_SINCE_LAST_START = 7 * 24
COUNT_WINDOWS_H = (1, 3, 24, 168)
RATE_DAYS = 28
RATE_DAYS_SHORT = 7
HOUR_RATE_PSEUDOCOUNT = 7  # згладжування частоти «та сама година доби» до 28-денної частоти

# Метрики
PROB_CLIP = 1e-6
BOOTSTRAP_REPS = 1000
CALIBRATION_BINS = 10
SEED = 0

# Моделі: підбір гіперпараметрів і ваги свіжих даних на внутрішньому часовому спліті train фолду
INNER_VAL_DAYS = 14
WEIGHT_HALF_LIVES_DAYS = (None, 30)      # None = без ваг
LR_C_GRID = (0.01, 0.1, 1.0)
HGB_GRID = (
    dict(learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0),
    dict(learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=100, l2_regularization=1.0),
    dict(learning_rate=0.1, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=0.0),
    dict(learning_rate=0.1, max_leaf_nodes=31, min_samples_leaf=50, l2_regularization=0.0),
)
HGB_MAX_ITER = 500
