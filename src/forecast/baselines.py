"""Reference forecasts every model must beat (PLAN.md §6). Vectorised: one pass over all origins.

  persistence   tomorrow … D+7 look like day D
  recurrence27  day D+h looks like day D+h−27 (one solar rotation earlier; always in the past for h ≤ 7)
  trailing27    the mean of the last 27 days (current activity level, one rotation)
  climatology   the training-period mean for the target day's calendar month
"""
import pandas as pd

from src import config
from src.forecast.base import Forecaster, as_origins, stack

TARGETS = config.FORECAST_TARGETS


class Persistence(Forecaster):
    name = "persistence"

    def predict(self, daily, origins):
        origins = as_origins(daily, origins)
        now = daily.loc[origins, TARGETS]
        return stack(origins, {h: {t: now[t] for t in TARGETS} for h in config.FORECAST_LEADS})


class Recurrence27(Forecaster):
    name = "recurrence27"

    def predict(self, daily, origins):
        origins = as_origins(daily, origins)
        # value at D+h−27 = series shifted forward by 27−h days, read at D (daily grid is complete)
        lag = {h: daily[TARGETS].shift(config.RECURRENCE_DAYS - h).reindex(origins) for h in config.FORECAST_LEADS}
        return stack(origins, {h: {t: lag[h][t] for t in TARGETS} for h in config.FORECAST_LEADS})


class TrailingMean(Forecaster):
    def __init__(self, days: int = config.RECURRENCE_DAYS):
        self.days = days
        self.name = f"trailing{days}"

    def predict(self, daily, origins):
        origins = as_origins(daily, origins)
        mean = daily[TARGETS].rolling(self.days, min_periods=self.days // 2).mean().reindex(origins)
        return stack(origins, {h: {t: mean[t] for t in TARGETS} for h in config.FORECAST_LEADS})


class Climatology(Forecaster):
    name = "climatology"

    def fit(self, daily):
        self.monthly_ = daily[TARGETS].groupby(daily.index.month).mean()
        return self

    def predict(self, daily, origins):
        origins = as_origins(daily, origins)
        per_lead = {}
        for h in config.FORECAST_LEADS:
            month = (origins + pd.Timedelta(days=h)).month
            per_lead[h] = {t: self.monthly_[t].reindex(month).to_numpy() for t in TARGETS}
        return stack(origins, per_lead)
