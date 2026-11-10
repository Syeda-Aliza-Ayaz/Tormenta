"""Forecast features (PLAN.md §5): one row per issue day D, built ONLY from days ≤ D. Shared by training, the
backtest and the daily job, so they can never disagree.

Base features (the same for every lead day):
  {ap,kpmax}_lag0..6      the last 7 days
  ap_mean3/7/27, kpmax_mean27, kpmax_max7, ap_std7
  f107, f107_mean81       solar activity level (trailing; last value carried at most 7 days)
Lead-specific features (lead day h; all in the past because h ≤ 7 < 26):
  {ap,kpmax}_rec27        value one solar rotation before the target day (D+h−27)
  ap_rec27w               mean of D+h−28 … D+h−26 (rotation period jitters by a day or so)
  ap_rec54, ap_rec81      two and three rotations before
  doy_sin, doy_cos        season of the TARGET day (calendar, known in advance)
"""
import numpy as np
import pandas as pd

from src import config

LAGS = range(7)


def base_features(daily: pd.DataFrame) -> pd.DataFrame:
    ap, kp = daily["ap"], daily["kpmax"]
    f = {}
    for k in LAGS:
        f[f"ap_lag{k}"] = ap.shift(k)
        f[f"kpmax_lag{k}"] = kp.shift(k)
    f["ap_mean3"] = ap.rolling(3, min_periods=2).mean()
    f["ap_mean7"] = ap.rolling(7, min_periods=5).mean()
    f["ap_mean27"] = ap.rolling(27, min_periods=20).mean()
    f["ap_std7"] = ap.rolling(7, min_periods=5).std()
    f["kpmax_mean27"] = kp.rolling(27, min_periods=20).mean()
    f["kpmax_max7"] = kp.rolling(7, min_periods=5).max()
    f107 = daily["f107_obs"].ffill(limit=config.F107_MAX_STALE_DAYS)
    f["f107"] = f107
    f["f107_mean81"] = daily["f107_obs"].rolling(config.F107_TRAILING_DAYS, min_periods=40).mean()
    return pd.DataFrame(f, index=daily.index)


def lead_features(daily: pd.DataFrame, h: int) -> pd.DataFrame:
    ap, kp = daily["ap"], daily["kpmax"]
    r = config.RECURRENCE_DAYS
    f = {
        "ap_rec27": ap.shift(r - h),
        "ap_rec27w": pd.concat([ap.shift(r - h + d) for d in (-1, 0, 1)], axis=1).mean(axis=1),
        "kpmax_rec27": kp.shift(r - h),
        "ap_rec54": ap.shift(2 * r - h),
        "ap_rec81": ap.shift(3 * r - h),
    }
    doy = (daily.index + pd.Timedelta(days=h)).day_of_year.to_numpy()
    f["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    f["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return pd.DataFrame(f, index=daily.index)


def features(daily: pd.DataFrame, h: int) -> pd.DataFrame:
    """Feature matrix for lead day h, indexed by issue day D. The daily grid must be complete."""
    return pd.concat([base_features(daily), lead_features(daily, h)], axis=1)


def targets(daily: pd.DataFrame, h: int) -> pd.DataFrame:
    """What lead day h predicts for issue day D: the values on D+h (training only)."""
    return daily[config.FORECAST_TARGETS].shift(-h)
