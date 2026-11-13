"""Storm warnings (DECISIONS D-48): the fix for the imbalance problem.

The regression models forecast a typical value, so on rare storm days (max Kp ≥ 5−: 8–23% of days depending on the
solar cycle) they almost never reach the storm line (D-22). Here a separate CLASSIFIER per lead day gives
P(storm on D+h) from the same causal features (src/forecast/features.py), and the warning threshold is chosen for
rare events instead of 0.5:

  tune      fit on data ≤ 2007, predict 2008–2016, choose per lead day the threshold that maximises the Heidke skill
            score (catches vs false alarms); no resampling, so the probabilities stay honest
  validate  fit ≤ 2016, score 2017–2019 with those thresholds          (never used for any choice)
  produce   fit the production window (≤ 2019, D-27), save with the thresholds; score the recent hindcast

    python -m src.forecast.storm
"""
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from src import config, scorecard
from src.forecast import features as F

BUNDLE = config.MODELS_DIR / "forecast" / "storm.joblib"
PARAMS = {"learning_rate": 0.05, "max_iter": 300, "max_leaf_nodes": 15, "min_samples_leaf": 100,
          "l2_regularization": 1.0}           # fixed in advance, like the other models' defaults; not tuned
THRESHOLD_GRID = np.round(np.arange(0.05, 0.81, 0.01), 2)
TUNE_START, TUNE_END = "2008-01-01", "2016-12-31"
NAME = "storm_warning"


def _xy(daily: pd.DataFrame, h: int):
    X, kp = F.features(daily, h), F.targets(daily, h)["kpmax"]
    keep = kp.notna() & X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1)
    return X[keep], (kp[keep] >= config.STORM_THRESHOLD).astype(int)


class StormClassifier:
    name = NAME

    def __init__(self, params: dict = None):
        self.params = params or PARAMS
        self.thresholds_ = {h: 0.5 for h in config.FORECAST_LEADS}
        self.frozen = False

    def fit(self, daily: pd.DataFrame) -> "StormClassifier":
        if self.frozen:
            return self
        self.models_ = {}
        for h in config.FORECAST_LEADS:
            X, y = _xy(daily, h)
            self.models_[h] = HistGradientBoostingClassifier(**self.params, early_stopping=False,
                                                             random_state=config.RANDOM_STATE).fit(X, y)
        self.columns_ = list(X.columns)
        self.base_rate_ = float(y.mean())
        self.trained_until_ = str(daily.index.max().date())
        return self

    def predict(self, daily: pd.DataFrame, origins) -> pd.DataFrame:
        origins = pd.DatetimeIndex(origins)
        window = daily.loc[origins.min() - pd.Timedelta(days=130): origins.max()]
        parts = []
        for h in config.FORECAST_LEADS:
            X = F.features(window, h).reindex(origins)[self.columns_]
            p = self.models_[h].predict_proba(X)[:, 1]
            parts.append(pd.DataFrame({"origin": origins, "lead": h, "target_date": origins + pd.Timedelta(days=h),
                                       "storm_prob": p, "threshold": self.thresholds_[h],
                                       "warning": p >= self.thresholds_[h]}))
        return pd.concat(parts, ignore_index=True).sort_values(["origin", "lead"], ignore_index=True)

    def save(self, path=None, **meta):
        path = path or BUNDLE
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self, "sklearn_version": sklearn.__version__, **meta}, path)

    @staticmethod
    def load(path=None) -> "StormClassifier":
        model = joblib.load(path or BUNDLE)["model"]
        model.frozen = True
        return model


def tune_thresholds(fc: pd.DataFrame) -> dict:
    """Per lead day: the threshold with the best Heidke skill score (ties → the higher threshold, fewer alarms)."""
    out = {}
    for h, g in fc.groupby("lead"):
        obs = g["storm_obs"].to_numpy(bool)
        scores = [(scorecard.contingency(g["storm_prob"].to_numpy() >= t, obs)["hss"], t) for t in THRESHOLD_GRID]
        best = max(s for s, _ in scores if not np.isnan(s))
        out[int(h)] = float(max(t for s, t in scores if s == best))
    return out


def attach_obs(fc: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    kp = daily["kpmax"].reindex(fc["target_date"]).to_numpy()
    out = fc.assign(kpmax_obs=kp, obs_definitive=daily["definitive"].reindex(fc["target_date"]).fillna(False).to_numpy())
    out = out[out["kpmax_obs"].notna()]
    return out.assign(storm_obs=out["kpmax_obs"] >= config.STORM_THRESHOLD)


def table(fc: pd.DataFrame) -> pd.DataFrame:
    """Contingency counts + POD/FAR/HSS per lead, and the Brier score of the probabilities."""
    rows = []
    for h, g in fc.groupby("lead"):
        c = scorecard.contingency(g["warning"], g["storm_obs"])
        brier = float(np.mean((g["storm_prob"] - g["storm_obs"]) ** 2))
        rows.append({"model": NAME, "lead": int(h), "n": len(g), **c, "brier": brier,
                     "threshold": float(g["threshold"].iloc[0])})
    return pd.DataFrame(rows)


def main() -> dict:
    from src import backtest
    from src.daily import load_daily
    from src.issue import production_window

    daily = load_daily()
    out = config.FORECAST_REPORTS_DIR / "metrics"

    # 1. thresholds: fitted ≤ 2007, chosen on 2008–2016 (inside the training years)
    t0, t1 = pd.Timestamp(TUNE_START), pd.Timestamp(TUNE_END)
    tuner = StormClassifier().fit(backtest.training_rows(daily, t0))
    probs = attach_obs(tuner.predict(daily, backtest.origins_for(t0, t1)), daily)
    probs = probs[probs["target_date"].between(t0, t1) & probs["obs_definitive"]]
    thresholds = tune_thresholds(probs)
    print("thresholds by lead day (chosen on 2008-2016):", thresholds)

    # 2. validation 2017–2019: fitted ≤ 2016, thresholds fixed from step 1
    v0, v1 = backtest.period("validation", daily)
    val_model = StormClassifier().fit(backtest.training_rows(daily, v0))
    val_model.thresholds_ = thresholds
    val = attach_obs(val_model.predict(daily, backtest.origins_for(v0, v1)), daily)
    val = val[val["target_date"].between(v0, v1) & val["obs_definitive"]]
    val_table = table(val)
    val_table.to_csv(out / "validation_storm_warning.csv", index=False)

    # 3. production (≤ 2019) + recent hindcast
    prod = StormClassifier().fit(production_window(daily))
    prod.thresholds_ = thresholds
    prod.save(thresholds=thresholds)
    r0, r1 = backtest.period("recent", daily)
    rec = attach_obs(prod.predict(daily, backtest.origins_for(r0, r1)), daily)
    rec = rec[rec["target_date"].between(r0, r1)]
    rec_table = table(rec)
    rec_table.to_csv(out / "recent_storm_warning.csv", index=False)
    cols = ["lead", "hits", "misses", "false_alarms", "correct_negatives", "pod", "far", "hss", "threshold"]
    print("validation 2017-2019:\n", val_table[cols].round(2).to_string(index=False))
    print("recent:\n", rec_table[cols].round(2).to_string(index=False))
    return {"thresholds": thresholds, "validation": val_table, "recent": rec_table}


if __name__ == "__main__":
    from src.forecast import storm as _module      # pickle the class as src.forecast.storm, not __main__ (D-32)
    _module.main()
