"""Load the promoted model bundle and predict Kp with an 80% interval.

Phase 3: prediction from a feature matrix. Phase 4 adds the live SWPC path.
"""
import joblib
import numpy as np
import pandas as pd

from src import config


def load_bundle(path=config.CURRENT_MODEL) -> dict:
    return joblib.load(path)


def predict_with_interval(bundle: dict, X: pd.DataFrame) -> pd.DataFrame:
    """Point (squared-error HistGB) + q10/q90 band, widened to always contain the point."""
    X = X[bundle["features"]]
    point = bundle["point"].predict(X)
    lo = np.minimum(bundle["q_lo"].predict(X), point)
    hi = np.maximum(bundle["q_hi"].predict(X), point)
    clip = lambda a: np.clip(a, 0, 9)
    return pd.DataFrame({"kp_pred": clip(point), "kp_lo": clip(lo), "kp_hi": clip(hi)}, index=X.index)
