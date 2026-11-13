"""Portable model format: the fitted HistGradientBoosting trees as plain numpy arrays.

Why: the browser app (Hugging Face static Space, Streamlit running in Pyodide via stlite) cannot load the
scikit-learn 1.9.1 pickle, because Pyodide ships a different scikit-learn and pickles are not portable across
versions. The trees themselves are just numbers, so they are stored in an .npz file and walked with numpy.
tests/test_portable.py checks the predictions are identical to scikit-learn's.

Prediction rule (same as scikit-learn's TreePredictor, numeric features only):
    raw = baseline + sum over trees of the leaf value reached, where at each split
          NaN → left if missing_go_to_left else right;  x <= threshold → left;  else right.
For squared-error and pinball (quantile) losses the prediction is the raw value.
"""
import json
from pathlib import Path

import numpy as np

MODELS = ("point", "q_lo", "q_hi")
META_KEYS = ("features", "params", "interval_margin", "trained_until", "version", "sklearn_version", "monotonic")


def _flatten(model) -> dict:
    """All trees of one fitted HistGradientBoostingRegressor → concatenated node arrays + tree offsets."""
    if getattr(model, "is_categorical_", None) is not None and np.any(model.is_categorical_):
        raise ValueError("categorical features are not supported by the portable format")
    trees = [tree[0].nodes for tree in model._predictors]          # one tree per iteration (regression)
    offsets = np.cumsum([0] + [len(n) for n in trees])
    nodes = np.concatenate(trees)
    return {"feature": nodes["feature_idx"].astype(np.int32),
            "threshold": nodes["num_threshold"].astype(np.float64),
            "missing_left": nodes["missing_go_to_left"].astype(bool),
            "left": nodes["left"].astype(np.int32), "right": nodes["right"].astype(np.int32),
            "is_leaf": nodes["is_leaf"].astype(bool), "value": nodes["value"].astype(np.float64),
            "offsets": offsets.astype(np.int64),
            "baseline": np.asarray(model._baseline_prediction, dtype=np.float64).ravel()}


def save_portable(bundle: dict, path) -> Path:
    """Write a model bundle (point + q_lo + q_hi) as one .npz with a JSON metadata entry."""
    arrays = {f"{m}__{k}": v for m in MODELS for k, v in _flatten(bundle[m]).items()}
    meta = {k: bundle.get(k) for k in META_KEYS}
    arrays["meta"] = np.frombuffer(json.dumps(meta, default=str).encode("utf-8"), dtype=np.uint8)
    path = Path(path)
    np.savez_compressed(path, **arrays)
    return path


class TreeEnsemble:
    """numpy re-implementation of a fitted HistGradientBoostingRegressor's predict()."""

    def __init__(self, arrays: dict):
        self.a = arrays

    def predict(self, X) -> np.ndarray:
        X = np.asarray(X, dtype=np.float64)
        a, rows = self.a, np.arange(len(X))
        out = np.full(len(X), a["baseline"][0])
        for start in a["offsets"][:-1]:
            node = np.full(len(X), start)
            active = ~a["is_leaf"][node]
            while active.any():
                n = node[active]
                x = X[rows[active], a["feature"][n]]
                go_left = np.where(np.isnan(x), a["missing_left"][n], x <= a["threshold"][n])
                node[active] = start + np.where(go_left, a["left"][n], a["right"][n])
                active = ~a["is_leaf"][node]
            out += a["value"][node]
        return out


def load_portable(path) -> dict:
    """A bundle dict usable by predict.predict_with_interval / predict_steady / predict_hourly."""
    with np.load(path) as z:
        data = {k: z[k] for k in z.files}
    meta = json.loads(data.pop("meta").tobytes().decode("utf-8"))
    bundle = {m: TreeEnsemble({k.split("__", 1)[1]: v for k, v in data.items() if k.startswith(f"{m}__")})
              for m in MODELS}
    return {**bundle, **meta, "portable": True}

