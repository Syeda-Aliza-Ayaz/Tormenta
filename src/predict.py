"""Load the promoted model bundle and predict Kp with an 80% interval.

Two entry points, both through the shared features.build_features:
  predict_with_interval(bundle, X)  — from a feature matrix (training/evaluation)
  nowcast()                         — live: SWPC → hourly → features → Kp + interval
"""
import warnings

import numpy as np
import pandas as pd

from src import config
from src.features import build_features


def load_bundle(path=config.CURRENT_MODEL) -> dict:
    """Load a model bundle; warn if this scikit-learn differs from the one it was trained with.

    Pickled estimators are only guaranteed to behave identically under the same version, which is why every
    deployment pins scikit-learn exactly.
    """
    import joblib                      # imported here so the browser app (portable model, no pickle) never needs it
    import sklearn

    bundle = joblib.load(path)
    trained = bundle.get("sklearn_version")
    if trained and trained != sklearn.__version__:
        warnings.warn(f"model trained with scikit-learn {trained} but running {sklearn.__version__}; "
                      "install the pinned version from requirements.txt", RuntimeWarning, stacklevel=2)
    return bundle


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


# ── Manual input (all three apps) ────────────────────────────────────────────
# Physical limits for a single hourly value; anything outside is almost certainly a typo.
INPUT_LIMITS = {
    "b_scalar": (0.1, 200.0, "|B| (nT)"), "bx": (-200.0, 200.0, "Bx GSM (nT)"),
    "by_gsm": (-200.0, 200.0, "By GSM (nT)"), "bz_gsm": (-200.0, 200.0, "Bz GSM (nT)"),
    "speed": (200.0, 3000.0, "speed (km/s)"), "density": (0.01, 200.0, "density (cm⁻³)"),
    "temperature": (1e3, 1e8, "temperature (K)"), "f107": (50.0, 500.0, "F10.7 (sfu)"),
}


def validate_inputs(raw: dict) -> tuple[dict, dict]:
    """Parse and check manual inputs → (values, errors). Errors map field → message."""
    values, errors = {}, {}
    for field, (lo, hi, label) in INPUT_LIMITS.items():
        text = str(raw.get(field, "")).strip()
        if not text:
            errors[field] = f"{label} is required."
            continue
        try:
            v = float(text)
        except ValueError:
            errors[field] = f"{label} must be a number."
            continue
        if not np.isfinite(v) or not lo <= v <= hi:
            errors[field] = f"{label} must be between {lo:g} and {hi:g}."
        else:
            values[field] = v
    if not errors:
        vector = np.sqrt(values["bx"] ** 2 + values["by_gsm"] ** 2 + values["bz_gsm"] ** 2)
        if vector > 1.05 * values["b_scalar"] + 0.5:
            errors["b_scalar"] = (f"|B| ({values['b_scalar']:g} nT) cannot be smaller than the size of its "
                                  f"components ({vector:.1f} nT).")
    return values, errors


def predict_steady(bundle: dict, values: dict, when=None) -> dict:
    """Kp for manually entered values, assuming they held steady for the past 3 days.

    The model also uses lags and 24-h averages, which one set of numbers cannot provide; repeating the
    values gives them a defined meaning (steady conditions) and still runs the shared build_features.
    """
    when = (pd.Timestamp.now("UTC").tz_localize(None) if when is None else pd.Timestamp(when)).floor("h")
    hours = pd.date_range(when - pd.Timedelta(hours=72), when, freq="h")
    hourly = pd.DataFrame({c: values[c] for c in config.SW_FEATURES}, index=hours)
    days = pd.date_range(when.normalize() - pd.Timedelta(days=120), when.normalize(), freq="D")
    f107 = pd.Series(values["f107"], index=days)
    row = predict_with_interval(bundle, build_features(hourly, f107).iloc[[-1]]).iloc[0]
    return {"time": f"{when:%Y-%m-%d %H:00} UTC", **{k: round(float(row[k]), 2) for k in row.index},
            "level": storm_level(row["kp_pred"])}


def storm_level(kp: float) -> str:
    """NOAA level label for a Kp value (0-3, 4, 5 (G1), …)."""
    return str(pd.cut([kp], config.KP_BINS, labels=config.KP_BIN_LABELS, right=False)[0])
