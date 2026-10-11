"""Завантаження волонтерського датасету (eTryvoga) і «зріз станом на момент»."""
import pandas as pd

from .config import EXCLUDE

REQUIRED = ["region", "started_at", "finished_at", "naive"]


def load_events(path, exclude=EXCLUDE):
    df = pd.read_csv(path)
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        raise ValueError(f"У файлі немає колонок {sorted(missing)}; є {list(df.columns)}")
    df = df[REQUIRED].copy()
    for c in ("started_at", "finished_at"):
        df[c] = pd.to_datetime(df[c], utc=True).dt.as_unit("ns")  # pandas 3 інакше може взяти "us"
    df["naive"] = df["naive"].astype(str).str.strip().str.lower().eq("true")
    df = df[~df.region.isin(exclude)]
    return df.sort_values(["region", "started_at"]).reset_index(drop=True)


def cut_events(events, cutoff):
    """Те, що було відомо в момент cutoff: лише старти < cutoff; кінець, що ще не настав, невідомий (NaT)."""
    ev = events[events.started_at < cutoff].copy()
    ev.loc[ev.finished_at.isna() | (ev.finished_at >= cutoff), "finished_at"] = pd.NaT
    return ev.reset_index(drop=True)
