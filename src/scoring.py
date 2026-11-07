"""Lightweight scoring helpers (numpy/pandas only).

Kept separate from evaluate.py (which needs scikit-learn and matplotlib for plots and permutation importance) so
the browser app can import them without downloading those packages. evaluate.py re-exports both functions.
Formulas match sklearn.metrics exactly (tests/test_portable.py checks it).
"""
import numpy as np
import pandas as pd

from src import config


def metrics(y, pred) -> dict:
    """Overall RMSE/MAE/R² plus RMSE/MAE on storm hours (Kp ≥ 5-)."""
    y, pred = np.asarray(y, dtype=float), np.asarray(pred, dtype=float)
    err = pred - y
    storm = y >= config.STORM_THRESHOLD
    ss_tot = np.sum((y - y.mean()) ** 2)
    return {
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "r2": float(1 - np.sum(err ** 2) / ss_tot) if ss_tot > 0 else np.nan,
        "storm_rmse": float(np.sqrt(np.mean(err[storm] ** 2))) if storm.any() else np.nan,
        "storm_mae": float(np.mean(np.abs(err[storm]))) if storm.any() else np.nan,
        "n": len(y),
    }


def attach_block_kp(pred: pd.DataFrame, kp_blocks: pd.Series, name: str) -> pd.DataFrame:
    """Add the Kp of the 3-h block containing each hour (e.g. NOAA estimated or GFZ Kp)."""
    block = pred.index.floor(f"{config.KP_BLOCK_HOURS}h")
    return pred.assign(**{name: kp_blocks.reindex(block).to_numpy()})
