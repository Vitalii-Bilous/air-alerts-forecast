# Forecasting air raid alert onsets in Ukrainian oblasts

Every hour, the model estimates the probability that **a new air raid alert starts in an oblast within the next H hours**. H=3 is the main horizon and H=1 is secondary. Forecasts cover 21 oblasts and are evaluated on the latest 4 weeks of data (2026-09-12 to 2026-10-10), with no peeking into the future.

**Test result (single run):** gradient boosting beats the strongest baseline (the oblast's alert rate over the last 7 or 28 days) by **4.5–4.8% in Brier score** at H=3 and by **4.0–4.2%** at H=1. The 95% confidence intervals exclude zero, and the model wins in each of the 4 test weeks. The gain is modest and comes almost entirely from regional alert dynamics. It is largest while an alert is already active. The model cannot predict the first alert after a quiet day.

## 1. Problem framing

- **Unit:** an (oblast, hour t) pair on an hourly UTC grid.
- **Target:** `y_H(t) = 1` if an alert starts in the oblast during `[t, t+H)`. The model outputs a probability, so this is probabilistic classification, not a count forecast.
- **Why this target:** it answers a practical question ("will there be an alert soon?") and has honest metrics (Brier score, calibration). Why alert duration and alert counts were not chosen is explained in [docs/01](docs/01_problem_framing.md).
- **Region groups** were fixed geographically before any results were seen: front (8), center (8, including Odesa), west (5). At H=3 the task is nearly trivial on the front (base rate up to 0.9 in Kharkiv and Dnipropetrovsk oblasts), so H=1 is reported separately.
- Hour of day and day of week are taken in Kyiv time.

## 2. Data and its problems

Source: [Vadimkin/ukrainian-air-raid-sirens-dataset](https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset). The main dataset is the volunteer eTryvoga feed (`volunteer_data_en.csv`: `region, started_at, finished_at, naive`), because the official dataset ends on 2026-09-07. The official data is used only for cross-checks. A snapshot taken on 2026-10-11 is in `data/` (sha256 `e441ecaa9813c908…`), because the source dataset is updated daily.

The data was checked before modelling ([docs/02](docs/02_data_checks.md), [docs/03](docs/03_data_fixes_and_long_alerts.md), scripts in `docs/checks/`):
- **Lviv oblast since 11.2025 and Volyn oblast since 09.2025 are corrupted.** Their volunteer alerts match alerts in specific raions of Odesa oblast (0.71) and Chernihiv oblast (Prylutskyi raion, 0.88). That is about 15 times more often than chance and about 4 times more often than for control oblasts. Both oblasts are excluded.
- **Zakarpattia** has no alerts at all after 2026-07-30, while the official data has 12 in August. **Luhansk** has only 3 records. Both are excluded, which leaves **21 oblasts**.
- **Missed all-clears:** western oblasts have alerts lasting 70–94 hours. Alerts longer than 6 hours are treated as a missed all-clear, and the affected rows are removed **from train only**. Donetsk and Zaporizhzhia are exempt, because their long alerts are real. On validation and test the primary metric uses **all** hours, because alert duration is unknown in real time. A metric without those hours is reported as a secondary check.
- `naive=True` means the alert end is synthetic (+30 min). Such an alert is treated as active until the next start.
- Activity grew strongly in 2026, and data from 2022 onward hurts. **Training starts on 2025-12-01** (chosen on validation).

## 3. Leakage-free evaluation

| Period | Dates (Kyiv) | Use |
|---|---|---|
| train | 2025-12-01 … 2026-08-15 | fitting |
| validation | 2026-08-15 … 2026-09-12 | choosing models and design decisions |
| test | 2026-09-12 … 2026-10-10 | **opened once**, after writing down the hypothesis ([docs/09](docs/09_pretest_hypothesis.md)) |

- **Weekly refits (rolling origin).** There are 4 one-week folds. For each week, the model is trained on all data from 2025-12-01 up to the start of that week. Each boundary has an H-hour purge, so the label of the last training row is already known.
- **Features use only the past:** alert starts before t and alert ends known before t. Rates are computed from labels already known at t (`shift(H)`). The long-alert mask on train is computed as of the fold start.
- **Hyperparameters and recency weights** are chosen in each fold on an inner temporal split (the last 14 days of the fold's train), never on validation or test. Early stopping in boosting also uses a temporal split, not a random one.
- **Automated tests** (`tests/test_leakage.py`). The main one is a "corrupt the future" test: events after t0 are removed or altered, and the features (for any t0) and every model's predictions (for t0 after the fold boundary) must stay identical. Other tests cover fold boundaries and purge, the as-of long-alert mask, and the test-period lock. Mutation checks confirmed that the tests catch deliberately injected leakage.
- **Test lock:** without the `--final-test` flag, the code drops every event after the end of validation before the grid is built.

**Metrics:** Brier score (primary) and Brier skill score (BSS) relative to `clim_28d`, a reference fixed in advance. Also log loss, PR-AUC and calibration (ECE, 10 bins). 95% confidence intervals come from a day-block bootstrap (1000 resamples).

## 4. Models

| Name | What it is |
|---|---|
| `clim_28d` | share of hours with an alert start in the oblast over the last 28 days (BSS reference) |
| `clim_7d` | the same over 7 days; the strongest baseline on validation |
| `clim_28d_hour`, `clim_train`, `recent_start` | other simple baselines |
| `logreg` | logistic regression: standardization, sin/cos time, one-hot oblast, L2 |
| **`hgb`** | scikit-learn `HistGradientBoostingClassifier`, **the main model** |

Both models are shared across all 21 oblasts. Features (`alerts/features.py`):
- regional: whether an alert is active at t, minutes since it started, hours since the last start, number of starts in the last 1/3/24/168 h, 7- and 28-day rates, rate for the same hour of day;
- country and group level: how many oblasts are under alert now, number of starts in the last 1–24 h;
- hour of day and day of week.

## 5. Results

### Test (all hours, 21 oblasts)

| H | Model | Brier | BSS vs `clim_28d` | BSS vs `clim_7d` | ECE |
|---|---|---|---|---|---|
| 3 | clim_28d | 0.1835 | 0 | | 0.030 |
| 3 | clim_7d | 0.1841 | −0.003 [−0.013, +0.007] | 0 | 0.020 |
| 3 | logreg | 0.1757 | +0.043 [+0.030, +0.055] | | 0.026 |
| 3 | **hgb** | **0.1753** | **+0.045 [+0.030, +0.060]** | **+0.048 [+0.032, +0.065]** | 0.017 |
| 1 | clim_28d | 0.1583 | 0 | | 0.014 |
| 1 | logreg | 0.1525 | +0.037 [+0.029, +0.044] | | 0.007 |
| 1 | **hgb** | **0.1519** | **+0.040 [+0.031, +0.049]** | **+0.042 [+0.030, +0.052]** | 0.007 |

Without the long-alert hours the numbers barely change: hgb at H=3 gets +0.045 [+0.031, +0.059].

### Validation vs test (hgb, BSS)

| | Validation | Test |
|---|---|---|
| H=3, vs clim_28d | +0.061 [+0.042, +0.082] | +0.045 [+0.030, +0.060] |
| H=3, vs clim_7d | +0.045 [+0.018, +0.071] | +0.048 [+0.032, +0.065] |
| H=1, vs clim_28d | +0.044 [+0.036, +0.051] | +0.040 [+0.031, +0.049] |
| H=3, hgb vs logreg | +0.019 [+0.007, +0.032] | +0.002 [−0.007, +0.012] |

### Where the model helps (test, hgb vs clim_7d)

| Situation | H=1 | H=3 |
|---|---|---|
| alert already active in the oblast (32% of hours) | +0.094 [+0.071, +0.119] | +0.059 [+0.037, +0.084] |
| oblast quiet (68%) | +0.024 [+0.012, +0.034] | +0.042 [+0.023, +0.064] |
| no alert start in the last 24 h (11%) | +0.015 [−0.028, +0.061] | −0.014 [−0.073, +0.034] |

By group (H=3, vs `clim_28d`): front +0.070, center +0.036, west +0.013 (the CI crosses 0). Weekly and per-oblast details are in [docs/10](docs/10_test_results.md).

### Conclusions
1. **The hypotheses written down before the test held:** hgb beats both baselines at H=3 and H=1. On validation the model lost to `clim_7d` during a surge week, but that risk did not materialize on test.
2. **What did not hold:** boosting's edge over logistic regression. On test the two are tied, so the gain comes from the **features**, not the choice of model.
3. The main thing the model learned is **the mechanics of a sequential alert stream**: while an alert is active, a new start within the next hour is less likely. The baselines cannot see this.
4. Country-level features add almost nothing: only +0.005 BSS in the validation ablation ([docs/08](docs/08_validation_analysis.md)). They were kept to avoid tuning the model to validation.

## 6. Limitations

- **The target is the volunteer eTryvoga stream, not official data.** In August 2026 only 46% of its starts match an official start within ±3 minutes, and 21% fall during an already active official alert. The model forecasts this specific stream.
- **I saw aggregates from the test period before opening the test:** while checking the data I looked at monthly alert counts for September. No decisions were based on them, but the test is not fully blind.
- 4 test weeks are not enough for conclusions about individual oblasts. Kyiv oblast and Ternopil were among the best on validation but slightly worse than `clim_7d` on test.
- Activity drifts strongly, so the model needs regular refits. The evaluation protocol does exactly that, weekly.
- There are no forecasts for Lviv, Volyn, Zakarpattia and Luhansk oblasts, because they were excluded.

## 7. Text data (not implemented)

Text sources (news, Telegram, official statements) were deliberately left out: in the time available, the leakage risk outweighed the likely gain. To add them honestly:
1. Use only messages with **publication time < t**, not the time of the event they describe. For edited posts, use the first version.
2. Aggregate them into features on the (oblast, hour) grid, e.g. the number of mentions of "Shahed" or "launch" per oblast in the last hour, computed with the same as-of-t code.
3. Add these features to the "corrupt the future" test: messages after t0 must not change features before t0.
4. Do not use sources that publish after an alert has started (e.g. summary reports) without checking their publication delay.

## 8. How to run

```bash
pip install -r requirements.txt     # tested with Python 3.13, scikit-learn 1.9.1, pandas 3.0.5, numpy 2.5.3
python -m pytest -q tests                                          # 11 passed, 2 skipped (~2 min)
ALERTS_CSV=data/volunteer_data_en.csv python -m pytest -q tests    # 13 passed, ~4 min (adds real-data tests)
python run_eval.py --data data/volunteer_data_en.csv               # validation, ~5 min → results/val_*
python analysis/analyze_val.py --data data/volunteer_data_en.csv   # validation ablation and slices, ~3 min
python run_eval.py --data data/volunteer_data_en.csv --final-test  # test (reproduction; already run once)
python analysis/summarize_test.py                                  # paired comparisons and test slices
python predict_now.py --data data/volunteer_data_en.csv            # current forecast for all 21 oblasts, ~1 min
```

### Forecast for a given moment

`predict_now.py` retrains hgb from scratch on everything known at the forecast moment and prints, for every oblast, the probability of an alert start within 1 and 3 hours, next to the `clim_7d` baseline. By default the moment is the hour after the last record in the CSV. `--at "2026-10-05 18:00"` (Kyiv time) sets it explicitly, and `--out file.csv` saves the table. All events after the moment are dropped before the grid is built. `tests/test_predict_now.py` checks that corrupting everything after the moment does not change the forecast. To forecast the real present, download a fresh `volunteer_data_en.csv` from the dataset repository.

For temporal early stopping, boosting passes `X_val`/`y_val` to `HistGradientBoostingClassifier.fit`. If your scikit-learn version does not support this, upgrade it.

## 9. Layout

```
alerts/       code: config, data, grid (grid and labels), features, baselines, models, evaluate
run_eval.py   validation or test run
predict_now.py  forecast for a given moment
analysis/     validation analysis and test summary
tests/        leakage tests
data/         snapshot of the volunteer dataset from 2026-10-11
results/      metrics, predictions, calibration plots (val_* and test_*)
docs/         step-by-step working notes (in Ukrainian) with decisions and checks; docs/checks/ holds data-check scripts
```

## 10. How the project was built

The project was built step by step with an AI assistant (Claude), which wrote the code and notes. I made every decision (framing, split, data rules, models) myself after comparing 2–3 options, and I ran and checked the code locally. The notes in `docs/` are in chronological order and show which options were considered and what changed after each check, including corrected mistakes. The notes are in Ukrainian; code comments are in Ukrainian too.
