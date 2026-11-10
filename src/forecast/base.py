"""The interface every forecaster implements, so the backtest, the daily job and the apps treat them alike.

Contract (tests/test_forecast.py enforces it for every registered model):
  fit(daily)               learn from the rows given (the caller cuts them to the training period)
  predict(daily, origins)  for each origin day D, forecast D+1 … D+7 using ONLY rows on or before D
                           → long frame: origin, lead, target_date, ap, kpmax
"""
import numpy as np
import pandas as pd

from src import config

COLUMNS = ["origin", "lead", "target_date"] + config.FORECAST_TARGETS


class Forecaster:
    name = "base"

    def fit(self, daily: pd.DataFrame) -> "Forecaster":
        return self

    def predict(self, daily: pd.DataFrame, origins) -> pd.DataFrame:
        raise NotImplementedError


def as_origins(daily: pd.DataFrame, origins) -> pd.DatetimeIndex:
    origins = pd.DatetimeIndex(origins)
    missing = origins.difference(daily.index)
    if len(missing):
        raise ValueError(f"origins not in the daily table: {list(missing[:3])}…")
    return origins


def stack(origins: pd.DatetimeIndex, per_lead: dict) -> pd.DataFrame:
    """per_lead[h] = {target: array aligned with origins} → the long forecast frame."""
    parts = []
    for h in config.FORECAST_LEADS:
        part = pd.DataFrame({t: np.asarray(per_lead[h][t], dtype=float) for t in config.FORECAST_TARGETS})
        part.insert(0, "origin", origins)
        part.insert(1, "lead", h)
        part.insert(2, "target_date", origins + pd.Timedelta(days=h))
        parts.append(part)
    return pd.concat(parts, ignore_index=True).sort_values(["origin", "lead"], ignore_index=True)[COLUMNS]
