# Working notes (in Ukrainian)

Notes from each step in chronological order. They are working documents: they contain the options considered, the decisions made and corrections to earlier steps. Early numbers that were later corrected are marked in the files themselves.

| File | Contents |
|---|---|
| [01_problem_framing.md](01_problem_framing.md) | problem framing, target options |
| [02_data_checks.md](02_data_checks.md) | dataset checks, problematic oblasts |
| [03_data_fixes_and_long_alerts.md](03_data_fixes_and_long_alerts.md) | long-alert rule, Volyn and Lviv checks |
| [04_eval_design.md](04_eval_design.md) | evaluation framework and leakage protection design |
| [05_eval_baselines_results.md](05_eval_baselines_results.md) | baselines on validation, choice of training start |
| [06_models_design.md](06_models_design.md) | model design |
| [07_models_validation.md](07_models_validation.md) | models on validation |
| [08_validation_analysis.md](08_validation_analysis.md) | ablation, slices, strategy |
| [09_pretest_hypothesis.md](09_pretest_hypothesis.md) | hypothesis written before the test |
| [10_test_results.md](10_test_results.md) | test results |

The scripts in `checks/` verify the data and are not part of the pipeline. They need CSV files from the dataset repository: `volunteer_data_en.csv` (included in `data/`) and `official_data_en.csv` (download separately).
