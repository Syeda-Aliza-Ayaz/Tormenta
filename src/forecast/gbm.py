"""HistGradientBoosting, one model per lead day and target ("direct" multi-step forecasting; PLAN.md §6).

Seven independent models per target: lead day h learns features(D) → value on D+h. No model feeds on another's
output, so errors do not compound across days.

    python -m src.forecast.gbm        # tune on train, validation backtest vs baselines + NOAA, save the bundle
"""
import json

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import ParameterSampler, TimeSeriesSplit

from src import config
from src.forecast import features as F
from src.forecast.base import Forecaster, as_origins, stack

BUNDLE = config.MODELS_DIR / "forecast" / "histgb.joblib"
PARAMS_JSON = config.MODELS_DIR / "forecast" / "histgb_params.json"
DEFAULT_PARAMS = {"learning_rate": 0.05, "max_iter": 300, "max_leaf_nodes": 15, "min_samples_leaf": 100,
                  "l2_regularization": 1.0}
SEARCH_SPACE = {"learning_rate": [0.02, 0.03, 0.05, 0.08], "max_iter": [200, 400, 700],
                "max_leaf_nodes": [7, 15, 31], "min_samples_leaf": [50, 100, 200, 400],
                "l2_regularization": [0.0, 0.3, 1.0, 3.0]}


def _xy(daily: pd.DataFrame, h: int, target: str):
    X, y = F.features(daily, h), F.targets(daily, h)[target]
    keep = y.notna() & X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1)
    return X[keep], y[keep]


def _model(params: dict) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(**params, early_stopping=False, random_state=config.RANDOM_STATE)


class HistGBDirect(Forecaster):
    name = "histgb"

    def __init__(self, params: dict = None, log_ap: bool = False):
        self.params = params or {t: DEFAULT_PARAMS for t in config.FORECAST_TARGETS}
        self.log_ap = log_ap
        self.frozen = False        # a loaded production bundle is never refitted by fit() (DECISIONS D-27)

    def fit(self, daily):
        if self.frozen:
            return self
        self.models_ = {}
        for h in config.FORECAST_LEADS:
            for t in config.FORECAST_TARGETS:
                X, y = _xy(daily, h, t)
                y = np.log1p(y) if (t == "ap" and self.log_ap) else y
                self.models_[(h, t)] = _model(self.params[t]).fit(X, y)
        self.columns_ = list(X.columns)
        self.trained_until_ = str(daily.index.max().date())
        return self

    def predict(self, daily, origins):
        origins = as_origins(daily, origins)
        # features need up to 81 + 27 days of history before the earliest origin, nothing after the latest
        window = daily.loc[origins.min() - pd.Timedelta(days=130): origins.max()]
        per_lead = {}
        for h in config.FORECAST_LEADS:
            X = F.features(window, h).reindex(origins)
            per_lead[h] = {}
            for t in config.FORECAST_TARGETS:
                p = self.models_[(h, t)].predict(X[self.columns_])
                p = np.expm1(p) if (t == "ap" and self.log_ap) else p
                per_lead[h][t] = np.clip(p, 0, 400 if t == "ap" else 9)
        return stack(origins, per_lead)

    def save(self, path=None, **meta):
        path = path or BUNDLE                  # resolved at call time, so tests can point it elsewhere
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self, "sklearn_version": sklearn.__version__, **meta}, path)

    @staticmethod
    def load(path=None) -> "HistGBDirect":
        bundle = joblib.load(path or BUNDLE)
        model = bundle["model"]
        model.frozen = True
        return model


def tune(train: pd.DataFrame, target: str, h: int = 3, n_iter: int = 12, log_ap: bool = False) -> tuple:
    """Random search with time-ordered CV on the training years, on one representative lead day.
    Scored as RMSE on the original scale, so log and raw targets are comparable."""
    X, y = _xy(train, h, target)
    folds = list(TimeSeriesSplit(n_splits=config.CV_SPLITS).split(X))
    results = []
    for params in ParameterSampler(SEARCH_SPACE, n_iter=n_iter, random_state=config.RANDOM_STATE):
        errs = []
        for tr, te in folds:
            fit_y = np.log1p(y.iloc[tr]) if log_ap else y.iloc[tr]
            p = _model(params).fit(X.iloc[tr], fit_y).predict(X.iloc[te])
            p = np.expm1(p) if log_ap else p
            errs.append(np.sqrt(np.mean((p - y.iloc[te].to_numpy()) ** 2)))
        results.append({**params, "cv_rmse": float(np.mean(errs))})
    table = pd.DataFrame(results).sort_values("cv_rmse", ignore_index=True)
    best = {k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in table.iloc[0].drop("cv_rmse").items()}
    best = {k: (int(v) if k in ("max_iter", "max_leaf_nodes", "min_samples_leaf") else float(v)) for k, v in best.items()}
    return best, table


def load_params(path=None) -> tuple:
    path = path or PARAMS_JSON
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        return saved["params"], saved.get("log_ap", False)
    return None, False


# ── Day-3 run: tune → validation backtest → rule → production bundle ─────────
def _importance(model: "HistGBDirect", daily: pd.DataFrame, first, last, h: int, target: str) -> pd.DataFrame:
    from sklearn.inspection import permutation_importance
    X, y = _xy(daily, h, target)
    idx = X.index[(X.index + pd.Timedelta(days=h) >= first) & (X.index + pd.Timedelta(days=h) <= last)]
    est = model.models_[(h, target)]
    fit_y = np.log1p(y.loc[idx]) if (target == "ap" and model.log_ap) else y.loc[idx]
    imp = permutation_importance(est, X.loc[idx, model.columns_], fit_y, n_repeats=5,
                                 random_state=config.RANDOM_STATE, scoring="neg_root_mean_squared_error")
    return pd.DataFrame({"feature": model.columns_, "importance": imp.importances_mean, "lead": h,
                         "target": target}).sort_values("importance", ascending=False)


def main(retune: bool = True) -> dict:
    from src import backtest
    from src.daily import load_daily

    daily = load_daily()
    first, last = backtest.period("validation", daily)
    train = backtest.training_rows(daily, first)
    out = config.FORECAST_REPORTS_DIR / "metrics"
    out.mkdir(parents=True, exist_ok=True)

    # 1. tune on the training years only (time-ordered CV), raw vs log target for Ap
    saved, saved_log = load_params()
    if not retune and saved:
        chosen, log_ap = saved, saved_log
        print(f"reusing tuned settings from {PARAMS_JSON.name} (Ap target {'log1p' if log_ap else 'raw'})")
    else:
        chosen, log_ap = _tune_all(train, out)

    # 2. validation backtest: every model + NOAA, fitted on the training years
    return _validate_and_save(daily, first, last, train, out, chosen, log_ap)


def _tune_all(train: pd.DataFrame, out) -> tuple:
    params, tables = {}, []
    for target, log_ap in [("ap", False), ("ap", True), ("kpmax", False)]:
        best, table = tune(train, target, log_ap=log_ap)
        tables.append(table.assign(target=target, log_ap=log_ap))
        print(f"tuned {target} (log={log_ap}): CV RMSE {table['cv_rmse'].iloc[0]:.3f} with {best}")
        params[(target, log_ap)] = (best, table["cv_rmse"].iloc[0])
    pd.concat(tables).to_csv(out / "histgb_tuning.csv", index=False)
    log_ap = bool(params[("ap", True)][1] < params[("ap", False)][1])   # decided on CV, before validation
    chosen = {"ap": params[("ap", log_ap)][0], "kpmax": params[("kpmax", False)][0]}
    PARAMS_JSON.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_JSON.write_text(json.dumps({"params": chosen, "log_ap": log_ap}, indent=2), encoding="utf-8")
    print(f"Ap target: {'log1p' if log_ap else 'raw'} (lower CV RMSE)")
    return chosen, log_ap


def _validate_and_save(daily, first, last, train, out, chosen, log_ap) -> dict:
    from src import backtest, scorecard
    from src.forecast import registry
    from src.issue import production_window

    fc = backtest.run(registry.all_models(), daily, first, last)
    fc = pd.concat([fc, backtest.noaa_rows(daily, first, last)], ignore_index=True)
    leads, storms = scorecard.lead_table(fc), scorecard.storm_table(fc)
    leads.to_csv(out / "validation_leads.csv", index=False)
    storms.to_csv(out / "validation_storms.csv", index=False)

    # 3. the rule fixed before looking (DECISIONS D-31): mean Ap skill vs trailing27 over lead days 1-7 > 0
    ap = leads[(leads["model"] == "histgb") & (leads["target"] == "ap")]
    skill = float(ap["skill_vs_trailing27"].mean())
    passed = skill > 0
    print(f"HistGB validation: mean Ap skill vs trailing27 = {skill:+.3f} -> {'PASS' if passed else 'FAIL'}")

    # 4. which features matter (validation rows), lead 1 and lead 7
    model = HistGBDirect(chosen, log_ap=log_ap).fit(train)
    imp = pd.concat([_importance(model, daily, first, last, h, "ap") for h in (1, 7)])
    imp.to_csv(out / "histgb_importance.csv", index=False)

    # 5. production bundle on the fixed production window (train + validation), only if the rule passed
    if passed:
        prod = HistGBDirect(chosen, log_ap=log_ap).fit(production_window(daily))
        prod.save(validation_skill_vs_trailing27=skill, params=chosen, log_ap=log_ap)
        print(f"saved {BUNDLE} (trained until {prod.trained_until_})")
    elif BUNDLE.exists():
        BUNDLE.unlink()
    return {"leads": leads, "storms": storms, "skill": skill, "passed": passed, "importance": imp}


if __name__ == "__main__":
    import argparse
    # Run through the imported module, not __main__: a bundle pickled from here would otherwise record the class
    # as __main__.HistGBDirect and fail to load anywhere else (DECISIONS D-32)
    from src.forecast import gbm as _module
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse-params", action="store_true", help="skip tuning; use models/forecast/histgb_params.json")
    _module.main(retune=not ap.parse_args().reuse_params)
