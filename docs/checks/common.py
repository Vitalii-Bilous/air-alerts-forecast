"""Спільні константи для скриптів перевірок (не код проєкту)."""
import pandas as pd

KYIV = "Europe/Kyiv"
# Регіони, які виключаємо: Луганська (лише 3 записи, постійна тривога),
# Львівська та Волинська (зіпсовані волонтерські дані), Закарпатська (немає тривог після 2026-07-30).
EXCLUDE = ["Luhanska oblast", "Lvivska oblast", "Volynska oblast", "Zakarpatska oblast"]
FRONT = ["Chernihivska oblast", "Sumska oblast", "Kharkivska oblast", "Donetska oblast",
         "Zaporizka oblast", "Khersonska oblast", "Dnipropetrovska oblast", "Mykolaivska oblast"]
WEST = ["Volynska oblast", "Rivnenska oblast", "Lvivska oblast", "Ternopilska oblast",
        "Khmelnytska oblast", "Ivano-Frankivska oblast", "Zakarpatska oblast", "Chernivetska oblast"]
VAL_START = pd.Timestamp("2026-08-15", tz=KYIV).tz_convert("UTC")
LONG_ALERT_HOURS = 6  # правило для підозріло довгих тривог, див. step1c
LONG_ALERT_EXEMPT = ["Donetska oblast", "Zaporizka oblast"]  # там довгі тривоги справжні


def group(region):
    return "front" if region in FRONT else ("west" if region in WEST else "center")


def load(path):
    return pd.read_csv(path, parse_dates=["started_at", "finished_at"])
