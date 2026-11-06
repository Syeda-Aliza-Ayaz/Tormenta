"""Training pipeline: features → time split → baselines + 4 model families → tuning →
validation → single test evaluation → weighting ablation → production fit → save.

Run from the notebook (03_modeling.ipynb) step by step, or end-to-end:
    python -m src.train            # full run (~30–60 min on a 6-core laptop)
    python -m src.train --fast     # smoke test (~2 min)
"""
import argparse
import json
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.stats import loguniform
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit, cross_val_score
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from src import config
from src.evaluate import metrics, metrics_table
from src.features import build_features, monotonic_cst
from src.preprocessing import load_processed


# ── Data ─────────────────────────────────────────────────────────────────────
def load_xy():
    """Feature matrix, target and persistence baseline on definitive-label hours."""
    df = load_processed()
    f107_daily = df["f107_obs"].resample("D").first()
    X = build_features(df[config.SW_FEATURES], f107_daily)
    y = df[config.TARGET]

    # Persistence: Kp of the previous 3-h block (uses past Kp — baseline only, never a feature)
    prev_block = df.index.floor(f"{config.KP_BLOCK_HOURS}h") - pd.Timedelta(hours=config.KP_BLOCK_HOURS)
    persistence = pd.Series(y.reindex(prev_block).to_numpy(), index=df.index)

    keep = y.notna() & df["kp_definitive"]
    return X[keep], y[keep], persistence[keep].fillna(y[keep].median())


def split_masks(index: pd.DatetimeIndex) -> dict:
    year = index.year
    return {
        "train": year <= config.TRAIN_YEARS[1],
        "val": (year >= config.VAL_YEARS[0]) & (year <= config.VAL_YEARS[1]),
        "test": year >= config.TEST_START_YEAR,
    }


# ── Models ───────────────────────────────────────────────────────────────────
def _scaled(model):
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", model)])


def model_specs() -> dict:
    """Estimator, search space and row strides (tune on / fit on) per model family."""
    rs = config.RANDOM_STATE
    return {
        "Linear Regression": dict(est=_scaled(LinearRegression()), params=None,
                                  tune_stride=1, fit_stride=1, n_jobs=1),
        "KNN": dict(est=_scaled(KNeighborsRegressor()),
                    params={"model__n_neighbors": [10, 20, 40, 80], "model__weights": ["uniform", "distance"]},
                    n_iter=8, tune_stride=config.SUBSAMPLE_STRIDE, fit_stride=config.SUBSAMPLE_STRIDE,
                    n_jobs=config.N_JOBS),
        "SVR": dict(est=_scaled(SVR(cache_size=500)),
                    params={"model__C": loguniform(0.3, 10), "model__gamma": loguniform(3e-3, 1e-1),
                            "model__epsilon": [0.1, 0.3, 0.5]},
                    n_iter=6, tune_stride=config.SUBSAMPLE_STRIDE, fit_stride=config.SUBSAMPLE_STRIDE,
                    n_jobs=config.N_JOBS),
        "Random Forest": dict(
            est=Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("model", RandomForestRegressor(n_estimators=100, n_jobs=1, random_state=rs))]),
            params={"model__max_depth": [12, 18, 24], "model__min_samples_leaf": [5, 10, 20],
                    "model__max_features": [0.3, 0.5]},
            n_iter=5, tune_stride=config.RF_TUNE_STRIDE, fit_stride=1, n_jobs=config.N_JOBS),
        "HistGB": dict(
            est=Pipeline([("model", HistGradientBoostingRegressor(early_stopping=False, random_state=rs))]),
            params={"model__learning_rate": loguniform(0.03, 0.2), "model__max_iter": [200, 400, 700],
                    "model__max_leaf_nodes": [15, 31, 63], "model__min_samples_leaf": [20, 50, 100],
                    "model__l2_regularization": loguniform(1e-3, 10)},
            n_iter=config.HISTGB_N_ITER, tune_stride=1, fit_stride=1, n_jobs=2),  # HistGB is multithreaded
    }


def _constrain(est, columns, monotonic=None):
    """Apply (or clear) the physics monotonic constraints on a HistGB pipeline."""
    use = config.USE_MONOTONIC if monotonic is None else monotonic
    return est.set_params(model__monotonic_cst=monotonic_cst(columns) if use else None)


def _rows(mask, stride, fast):
    idx = np.flatnonzero(mask)
    return idx[:: stride * (6 if fast else 1)]


def tune_models(X, y, masks, fast=False, log=print, names=None) -> dict:
    """TimeSeriesSplit CV search within the training years; refit best params on train rows."""
    cv = TimeSeriesSplit(n_splits=3 if fast else config.CV_SPLITS)
    out = {}
    for name, spec in model_specs().items():
        if names is not None and name not in names:
            continue
        t0 = time.time()
        rows = _rows(masks["train"], spec["tune_stride"], fast)
        Xt, yt = X.iloc[rows], y.iloc[rows]
        base = clone(spec["est"])
        if name == "HistGB":
            _constrain(base, X.columns)
        if spec["params"] is None:
            scores = cross_val_score(base, Xt, yt, cv=cv, scoring="neg_root_mean_squared_error")
            best, cv_rmse = {}, -scores.mean()
        else:
            search = RandomizedSearchCV(base, spec["params"], n_iter=2 if fast else spec["n_iter"],
                                        cv=cv, scoring="neg_root_mean_squared_error", n_jobs=spec["n_jobs"],
                                        random_state=config.RANDOM_STATE, refit=False)
            search.fit(Xt, yt)
            best, cv_rmse = search.best_params_, -search.best_score_
        est = fit_model(name, best, X, y, masks["train"], fast)
        out[name] = {"estimator": est, "best_params": best, "cv_rmse": cv_rmse, "seconds": time.time() - t0}
        log(f"{name:18s} CV RMSE {cv_rmse:.3f}  ({time.time() - t0:5.0f} s)  {best}")
    return out


def fit_model(name, params, X, y, mask, fast=False, sample_weight=None, monotonic=None):
    """Fit one family with given params on the rows of `mask` (at that family's fit stride)."""
    spec = model_specs()[name]
    rows = _rows(mask, spec["fit_stride"], fast)
    est = clone(spec["est"]).set_params(**params)
    if name == "Random Forest":
        est.set_params(model__n_jobs=config.N_JOBS)
    if name == "HistGB":
        _constrain(est, X.columns, monotonic)
    kw = {} if sample_weight is None else {"model__sample_weight": sample_weight.iloc[rows].to_numpy()}
    return est.fit(X.iloc[rows], y.iloc[rows], **kw)


# ── Evaluation steps ─────────────────────────────────────────────────────────
def validation_table(tuned, X, y, masks, persistence) -> pd.DataFrame:
    """Val metrics + CV RMSE + train RMSE (strided sample) for the overfitting check."""
    val, tr = masks["val"], _rows(masks["train"], config.SUBSAMPLE_STRIDE, False)
    preds = {"Persistence (baseline)": persistence[val]}
    preds.update({n: r["estimator"].predict(X[val]) for n, r in tuned.items()})
    preds = with_ensemble(preds)
    table = metrics_table(y[val], preds)
    table["cv_rmse"] = pd.Series({n: r["cv_rmse"] for n, r in tuned.items()})
    table["train_rmse"] = pd.Series({n: metrics(y.iloc[tr], r["estimator"].predict(X.iloc[tr]))["rmse"]
                                     for n, r in tuned.items()})
    return table


def test_evaluation(tuned, X, y, masks, persistence, fast=False, log=print):
    """Refit every family on train+val with its tuned params, evaluate ONCE on test."""
    trval, test = masks["train"] | masks["val"], masks["test"]
    preds, models = {"Persistence (baseline)": persistence[test].to_numpy()}, {}
    for name, r in tuned.items():
        t0 = time.time()
        models[name] = fit_model(name, r["best_params"], X, y, trval, fast)
        preds[name] = models[name].predict(X[test])
        log(f"{name:18s} refit + test in {time.time() - t0:4.0f} s")
    preds = with_ensemble(preds)
    return metrics_table(y[test], preds), preds, models


def with_ensemble(preds: dict) -> dict:
    """Add an equal-weight average of the ensemble members (no weights are fitted, so no leakage)."""
    members = [m for m in config.ENSEMBLE_MEMBERS if m in preds]
    if len(members) == len(config.ENSEMBLE_MEMBERS):
        preds = dict(preds)
        preds["Ensemble (HistGB+RF+SVR)"] = np.mean([np.asarray(preds[m]) for m in members], axis=0)
    return preds


def kp_history_ablation(best_params, X, y, masks, kp_feats, fast=False):
    """ABLATION ONLY: HistGB on solar wind vs solar wind + past Kp; trained on train, scored on val."""
    train, val = masks["train"], masks["val"]
    Xk = pd.concat([X, kp_feats], axis=1)
    preds = {"HistGB (solar wind only)": fit_model("HistGB", best_params, X, y, train, fast).predict(X[val]),
             "HistGB + past Kp (ablation)": fit_model("HistGB", best_params, Xk, y, train, fast).predict(Xk[val])}
    return metrics_table(y[val], preds), preds


def weighting_ablation(best_params, X, y, masks, fast=False):
    """HistGB unweighted vs storm-weighted (w = 1 + Kp/3), both trained on train+val."""
    trval, test = masks["train"] | masks["val"], masks["test"]
    w = config.SAMPLE_WEIGHT(y)
    preds = {"HistGB (unweighted)": fit_model("HistGB", best_params, X, y, trval, fast).predict(X[test]),
             "HistGB (weighted 1+Kp/3)": fit_model("HistGB", best_params, X, y, trval, fast,
                                                   sample_weight=w).predict(X[test])}
    return metrics_table(y[test], preds), preds


# ── Final round (v3): variants, diagnostics, interval calibration ───────────────
def compare_variant(best_params, X, y, masks, cols, monotonic, fast=False) -> dict:
    """HistGB with FIXED params on a column subset: CV RMSE (train years) + validation metrics."""
    Xc = X[cols]
    rows = _rows(masks["train"], 1, fast)
    est = _constrain(clone(model_specs()["HistGB"]["est"]).set_params(**best_params), cols, monotonic)
    cv = TimeSeriesSplit(n_splits=3 if fast else config.CV_SPLITS)
    cv_rmse = -cross_val_score(est, Xc.iloc[rows], y.iloc[rows], cv=cv, n_jobs=1,
                               scoring="neg_root_mean_squared_error").mean()
    model = fit_model("HistGB", best_params, Xc, y, masks["train"], fast, monotonic=monotonic)
    return {"cv_rmse": cv_rmse, **metrics(y[masks["val"]], model.predict(Xc[masks["val"]]))}


def learning_curve(best_params, X, y, masks, strides=(32, 16, 8, 4, 2, 1), monotonic=False, fast=False):
    """Train on every k-th training hour (less data); score train and validation RMSE."""
    out = {}
    for k in strides:
        rows = _rows(masks["train"], k, fast)
        est = fit_model("HistGB", best_params, X.iloc[rows], y.iloc[rows], np.ones(len(rows), bool),
                        monotonic=monotonic)
        out[len(rows)] = {"train_rmse": metrics(y.iloc[rows], est.predict(X.iloc[rows]))["rmse"],
                          "val_rmse": metrics(y[masks["val"]], est.predict(X[masks["val"]]))["rmse"]}
    return pd.DataFrame(out).T.rename_axis("training hours")


def complexity_curve(best_params, X, y, masks, leaves=(7, 15, 31, 63, 127, 255), monotonic=False, fast=False):
    """Vary tree size with everything else fixed: does a more complex model help validation?"""
    tr = _rows(masks["train"], config.SUBSAMPLE_STRIDE, False)
    out = {}
    for n in leaves:
        est = fit_model("HistGB", {**best_params, "model__max_leaf_nodes": n}, X, y, masks["train"], fast,
                        monotonic=monotonic)
        out[n] = {"train_rmse": metrics(y.iloc[tr], est.predict(X.iloc[tr]))["rmse"],
                  "val_rmse": metrics(y[masks["val"]], est.predict(X[masks["val"]]))["rmse"]}
    return pd.DataFrame(out).T.rename_axis("max_leaf_nodes")


def conformal_margin(best_params, X, y, masks, fast=False, log=print) -> tuple[float, pd.DataFrame]:
    """Conformalized quantile regression (CQR) margin for the q10-q90 band.

    Conformity score = how far y falls outside the band (negative if inside). Scores come only from
    predictions on data the quantile models did NOT train on: out-of-fold TimeSeriesSplit folds of
    the training years (skipping the first, tiny-training fold) plus the validation years (models
    trained on the training years). The margin is the 80% conformal quantile of those scores and is
    added to both sides of the band. Test and gate-holdout data are never used.
    """
    params = {k.removeprefix("model__"): v for k, v in best_params.items()}
    cst = monotonic_cst(X.columns) if config.USE_MONOTONIC else None

    def band(fit_idx, pred_idx):
        return [HistGradientBoostingRegressor(loss="quantile", quantile=q, early_stopping=False,
                                              random_state=config.RANDOM_STATE, monotonic_cst=cst, **params)
                .fit(X.iloc[fit_idx], y.iloc[fit_idx]).predict(X.iloc[pred_idx]) for q in config.QUANTILES]

    train_idx = _rows(masks["train"], 1, fast)
    folds = list(TimeSeriesSplit(n_splits=3 if fast else config.CV_SPLITS).split(train_idx))
    pieces = [(train_idx[a], train_idx[b]) for a, b in folds[config.CONFORMAL_SKIP_FOLDS:]]
    pieces.append((train_idx, _rows(masks["val"], 1, fast)))
    scores, rows = [], {}
    for fit_idx, pred_idx in pieces:
        t0 = time.time()
        lo, hi = band(fit_idx, pred_idx)
        yt = y.iloc[pred_idx].to_numpy()
        s = np.maximum(lo - yt, yt - hi)
        scores.append(s)
        idx = y.index[pred_idx]
        label = f"{idx.min():%Y-%m} to {idx.max():%Y-%m}"
        rows[label] = {"raw_coverage": float((s <= 0).mean()), "n": len(s)}
        log(f"calibration block {label}: raw coverage {(s <= 0).mean():.1%} ({time.time() - t0:.0f} s)")
    all_scores = np.concatenate(scores)
    level = config.QUANTILES[1] - config.QUANTILES[0]
    margin = float(np.quantile(all_scores, min(1.0, np.ceil((len(all_scores) + 1) * level) / len(all_scores))))
    table = pd.DataFrame(rows).T
    table["calibrated_coverage"] = [float((s <= margin).mean()) for s in scores]
    return margin, table


# ── Production model ─────────────────────────────────────────────────────────
def fit_bundle(best_params, X, y, mask, fast=False, sample_weight=None, margin=0.0) -> dict:
    """Point + q10/q90 HistGB trained on the rows of `mask` (+ conformal margin), packaged for predict.py."""
    params = {k.removeprefix("model__"): v for k, v in best_params.items()}
    rows = _rows(mask, 1, fast)
    Xf, yf = X.iloc[rows], y.iloc[rows]
    w = None if sample_weight is None else sample_weight.iloc[rows].to_numpy()

    rs = config.RANDOM_STATE
    cst = monotonic_cst(X.columns) if config.USE_MONOTONIC else None
    point = HistGradientBoostingRegressor(early_stopping=False, random_state=rs, monotonic_cst=cst,
                                          **params).fit(Xf, yf, sample_weight=w)
    q_lo, q_hi = (HistGradientBoostingRegressor(loss="quantile", quantile=q, early_stopping=False,
                                                random_state=rs, monotonic_cst=cst, **params).fit(Xf, yf)
                  for q in config.QUANTILES)
    return {
        "point": point, "q_lo": q_lo, "q_hi": q_hi,
        "features": list(X.columns), "params": params, "weighted": sample_weight is not None,
        "monotonic": cst is not None, "interval_margin": float(margin),
        "trained_until": str(y.index[rows].max()), "sklearn_version": sklearn.__version__,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _holdout_mask(y):
    return y.index >= y.index.max() - pd.DateOffset(months=config.GATE_HOLDOUT_MONTHS)


def gate_metrics(bundle, X, y) -> dict:
    """Score a bundle on the current gate holdout (the most recent 6 months of definitive labels)."""
    from src.predict import predict_with_interval
    hold = _holdout_mask(y)
    band = predict_with_interval(bundle, X[hold])
    gate = metrics(y[hold], band["kp_pred"])
    gate["coverage_80"] = float(((y[hold] >= band["kp_lo"]) & (y[hold] <= band["kp_hi"])).mean())
    gate["holdout"] = f"{y.index[hold].min()} → {y.index[hold].max()}"
    return gate


def fit_production(best_params, X, y, fast=False, sample_weight=None, margin=0.0):
    """Bundle trained up to the gate-holdout start (no refit-on-all); gate metrics on the holdout."""
    bundle = fit_bundle(best_params, X, y, ~_holdout_mask(y), fast, sample_weight, margin)
    return bundle, gate_metrics(bundle, X, y)


def gate_decision(candidate_gate: dict, X, y) -> tuple[bool, dict | None]:
    """Promote if candidate RMSE ≤ incumbent RMSE × tolerance, both scored on THIS run's holdout.

    The incumbent must not have been trained on the holdout; its stored trained_until is checked.
    """
    if not config.CURRENT_MODEL.exists():
        return True, None
    from src.predict import load_bundle
    incumbent = load_bundle()
    hold_start = y.index[_holdout_mask(y)].min()
    assert pd.Timestamp(incumbent["trained_until"]) < hold_start, "incumbent was trained on the holdout"
    inc = gate_metrics(incumbent, X, y)
    return candidate_gate["rmse"] <= inc["rmse"] * config.GATE_TOLERANCE, inc


def save_bundle(bundle, test_metrics: dict, gate_metrics: dict, promote: bool = True,
                incumbent_gate: dict | None = None, keep_rejected: bool = True, note: str | None = None) -> str:
    """Versioned model file (+ current.joblib if promoted) and an entry in metrics_history.json.

    keep_rejected=False (weekly retrain) logs a rejected candidate without writing its model file.
    """
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    version = f"tormenta_v{datetime.now(timezone.utc):%Y%m%d_%H%M}"
    bundle["version"] = version
    if promote or keep_rejected:
        joblib.dump(bundle, config.MODELS_DIR / f"{version}.joblib", compress=3)
    if promote:
        joblib.dump(bundle, config.CURRENT_MODEL, compress=3)

    history = json.loads(config.METRICS_HISTORY.read_text()) if config.METRICS_HISTORY.exists() else []
    clean = lambda d: {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in d.items()}
    history.append({"version": version, "created_utc": bundle["created_utc"],
                    "trained_until": bundle["trained_until"], "params": bundle["params"],
                    "weighted": bundle["weighted"], "n_features": len(bundle["features"]),
                    "test": clean(test_metrics), "gate": clean(gate_metrics),
                    "incumbent_gate": clean(incumbent_gate) if incumbent_gate else None,
                    "promoted": promote, **({"note": note} if note else {})})
    config.METRICS_HISTORY.write_text(json.dumps(history, indent=2, default=str))
    return version


def run(fast=False):
    """End-to-end run (same steps as the notebook)."""
    X, y, persistence = load_xy()
    masks = split_masks(X.index)
    print(f"{X.shape[1]} features | train {masks['train'].sum():,} | val {masks['val'].sum():,} | "
          f"test {masks['test'].sum():,} hours")
    tuned = tune_models(X, y, masks, fast)
    print(validation_table(tuned, X, y, masks, persistence).round(3))
    test_table, _, _ = test_evaluation(tuned, X, y, masks, persistence, fast)
    print(test_table.round(3))
    best = tuned["HistGB"]["best_params"]
    margin, _ = conformal_margin(best, X, y, masks, fast)
    bundle, gate = fit_production(best, X, y, fast, margin=margin)
    promote, incumbent = gate_decision(gate, X, y)
    version = save_bundle(bundle, test_table.loc["HistGB"].to_dict(), gate, promote, incumbent)
    print(f"Saved {version} (promoted={promote}); gate: {gate}; incumbent: {incumbent}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="tiny search + heavy subsampling (smoke test)")
    run(ap.parse_args().fast)
