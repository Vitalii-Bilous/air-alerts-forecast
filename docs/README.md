# Робочі нотатки

Нотатки кожного кроку в хронологічному порядку. Це робочі документи: у них є варіанти, які розглядались, рішення та виправлення попередніх кроків. Ранні цифри, які пізніше було виправлено, позначено в самих файлах.

| Файл | Що всередині |
|---|---|
| [01_problem_framing.md](01_problem_framing.md) | постановка задачі, варіанти цілі |
| [02_data_checks.md](02_data_checks.md) | перевірка датасетів, проблемні області |
| [03_data_fixes_and_long_alerts.md](03_data_fixes_and_long_alerts.md) | правило для довгих тривог, перевірка Волинської і Львівської |
| [04_eval_design.md](04_eval_design.md) | дизайн каркасу оцінки й захисту від leakage |
| [05_eval_baselines_results.md](05_eval_baselines_results.md) | бейзлайни на validation, вибір початку train |
| [06_models_design.md](06_models_design.md) | дизайн моделей |
| [07_models_validation.md](07_models_validation.md) | моделі на validation |
| [08_validation_analysis.md](08_validation_analysis.md) | ablation, зрізи, стратегія |
| [09_pretest_hypothesis.md](09_pretest_hypothesis.md) | гіпотеза, записана до test |
| [10_test_results.md](10_test_results.md) | результати test |

Скрипти в `checks/` перевіряють дані й не є частиною пайплайна. Їм потрібні CSV з репозиторію датасету: `volunteer_data_en.csv` (є в `data/`) і `official_data_en.csv` (завантажте окремо).
