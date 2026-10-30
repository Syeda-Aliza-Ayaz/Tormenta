"""Load the promoted model bundle and predict Kp with an 80% interval.

Two entry points, both through the shared features.build_features:
  predict_with_interval(bundle, X)  — from a feature matrix (training/evaluation)
  nowcast()                         — live: SWPC → hourly → features → Kp + interval
"""
import joblib
import numpy as np
import pandas as pd

from src import config
from src.features import build_features


def load_bundle(path=config.CURRENT_MODEL) -> dict:
    return joblib.load(path)


def predict_with_interval(bundle: dict, X: pd.DataFrame) -> pd.DataFrame:
    """Point (squared-error HistGB) + q10/q90 band (+ conformal margin), widened to contain the point."""
    X = X[bundle["features"]]
    point = bundle["point"].predict(X)
    margin = bundle.get("interval_margin", 0.0)       # v1/v2 bundles have no margin
    lo = np.minimum(bundle["q_lo"].predict(X) - margin, point)
    hi = np.maximum(bundle["q_hi"].predict(X) + margin, point)
    clip = lambda a: np.clip(a, 0, 9)
    return pd.DataFrame({"kp_pred": clip(point), "kp_lo": clip(lo), "kp_hi": clip(hi)}, index=X.index)


def predict_hourly(bundle: dict, hourly: pd.DataFrame, f107_daily: pd.Series, now=None) -> pd.DataFrame:
    """Kp + interval for every hour that has a full feature history and current solar-wind data.

    The first MIN_HISTORY_HOURS hours only warm up the trailing windows. Hours without current
    Bz or speed get no prediction (a model fed only clock features would be misleading).
    `ahead` marks hours after the current UTC hour: propagated data arrives ~1 h before it
    reaches Earth, so the newest hour is a short-range forecast.
    """
    X = build_features(hourly, f107_daily)
    X = X.iloc[config.MIN_HISTORY_HOURS:]
    X = X[X["bz_gsm"].notna() & X["speed"].notna()]
    out = predict_with_interval(bundle, X)
    now = pd.Timestamp.now("UTC").tz_localize(None) if now is None else pd.Timestamp(now)
    out["ahead"] = out.index > now.floor("h")
    return out


def nowcast(bundle: dict | None = None, now=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Live nowcast: (predictions, hourly raw inputs) from the SWPC feeds."""
    from src.ingest import fetch_live
    bundle = load_bundle() if bundle is None else bundle
    hourly = fetch_live.fetch_solar_wind()
    return predict_hourly(bundle, hourly, fetch_live.fetch_f107(), now), hourly
