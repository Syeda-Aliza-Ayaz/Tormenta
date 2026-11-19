"""Solar-wind candidate in shadow mode (D-68 candidate, D-69 conditions).

The candidate is `sw_rec_poisson` from the yearly validation: the live HistGB features plus daily solar wind of the
issue day and the day before, the 27-day echo of the solar-wind speed, and Poisson loss. It is not shown as the
forecast. The daily job logs it next to the live model so the two can be compared on the same days.

  Training   OMNI daily summaries (src/ingest/sw_archive.daily_summary on the hourly OMNI table), the live HistGB
             settings, the same fitting window as the live models (definitive days up to PRODUCTION_END). Solar wind
             is blank where OMNI has none (before 1998, after the end of the local table), as in validation.
  Live       solar wind from forecasts/solar_wind_hourly.csv, the archive of NOAA's real-time feed.
  Fallback   with no usable solar wind on the issue day the candidate scores below the live model (D-69, `no_sw`),
             so the served forecast is the live HistGB forecast for that origin, and the row says so.

Files:
  models/forecast/sw_shadow.joblib   the fitted candidate (frozen; refitted only by `python -m src.forecast.sw_shadow`)
  forecasts/shadow_log.csv           APPEND-ONLY, one row per origin × lead day.
"""
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from src import backtest, config
from src.forecast import features as F, gbm, storm
from src.ingest import sw_archive

BUNDLE = config.MODELS_DIR / "forecast" / "sw_shadow.joblib"
NAME = "histgb_sw"
LOSS = {"loss": "poisson"}
DAY_COLS = ["sw_speed", "sw_speed_max", "sw_bz", "sw_bz_min", "sw_vbs", "sw_density", "sw_b", "sw_pressure_max"]
LOG_COLUMNS = ["issued_at", "origin", "model_version", "lead", "target_date", "sw_status", "echo_days_missing",
               "ap_sw", "kpmax_sw", "storm_prob_sw", "ap_live", "kpmax_live", "served", "ap", "kpmax"]
KEY = ["origin", "lead"]


def sw_features(daily: pd.DataFrame, h: int, sw: pd.DataFrame) -> pd.DataFrame:
    """Live HistGB features plus solar wind; `sw` holds daily summaries (any index, reindexed to `daily`).
    Same columns and definitions as validate_yearly.SolarWindRec."""
    sw = sw.reindex(daily.index)
    x = F.features(daily, h)
    for c in DAY_COLS:
        x[f"{c}_lag0"] = sw[c]
    for c in ("sw_speed", "sw_vbs"):
        x[f"{c}_lag1"] = sw[c].shift(1)
    x["sw_speed_change"] = sw["sw_speed"] - sw["sw_speed"].shift(1)
    r = config.RECURRENCE_DAYS
    x["sw_speed_rec27"] = sw["sw_speed"].shift(r - h)
    x["sw_speed_rec27w"] = pd.concat([sw["sw_speed"].shift(r - h + d) for d in (-1, 0, 1)], axis=1).mean(axis=1)
    x["sw_speed_max_rec27"] = sw["sw_speed_max"].shift(r - h)
    x["sw_by_rec27"] = sw["sw_by"].shift(r - h)
    x["sw_by_lag0"] = sw["sw_by"]
    return x


def omni_daily() -> pd.DataFrame:
    h = pd.read_csv(config.PROCESSED_CSV, usecols=["time", *sw_archive.COLUMNS], parse_dates=["time"]).set_index("time")
    return sw_archive.daily_summary(h)


class SolarWindShadow:
    name = NAME

    def fit(self, daily: pd.DataFrame, sw: pd.DataFrame, params: dict) -> "SolarWindShadow":
        """`daily` is the fitting window (backtest.training_rows, with lead-in days flagged)."""
        self.models_, self.classifiers_ = {}, {}
        for h in config.FORECAST_LEADS:
            X = sw_features(daily, h, sw)
            tgt = F.targets(daily, h)
            rows = X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1) & ~daily["lead_in"]
            for t in config.FORECAST_TARGETS:
                k = rows & tgt[t].notna()
                self.models_[(h, t)] = gbm._model({**params[t], **LOSS}).fit(X[k], tgt.loc[k, t])
            k = rows & tgt["kpmax"].notna()
            self.classifiers_[h] = HistGradientBoostingClassifier(
                **storm.PARAMS, early_stopping=False, random_state=config.RANDOM_STATE
            ).fit(X[k], (tgt.loc[k, "kpmax"] >= config.STORM_THRESHOLD).astype(int))
        self.columns_ = list(X.columns)
        self.trained_until_ = str(daily.index.max().date())
        self.version = f"{NAME}-{self.trained_until_}"
        return self

    def predict(self, daily: pd.DataFrame, origin: pd.Timestamp, sw: pd.DataFrame) -> pd.DataFrame:
        window = daily.loc[origin - pd.Timedelta(days=config.FORECAST_HISTORY_DAYS): origin]
        rows = []
        for h in config.FORECAST_LEADS:
            X = sw_features(window, h, sw).loc[[origin], self.columns_]
            rows.append({"lead": h, "target_date": origin + pd.Timedelta(days=h),
                         "ap_sw": float(np.clip(self.models_[(h, "ap")].predict(X)[0], 0, 400)),
                         "kpmax_sw": float(np.clip(self.models_[(h, "kpmax")].predict(X)[0], 0, 9)),
                         "storm_prob_sw": float(self.classifiers_[h].predict_proba(X)[0, 1])})
        return pd.DataFrame(rows)

    def save(self, path=None):
        path = path or BUNDLE
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self, "sklearn_version": sklearn.__version__}, path)

    @staticmethod
    def load(path=None) -> "SolarWindShadow":
        return joblib.load(path or BUNDLE)["model"]


def issue(daily: pd.DataFrame, origin: pd.Timestamp, live: pd.DataFrame, archive: pd.DataFrame,
          issued_at: pd.Timestamp, model: SolarWindShadow = None) -> pd.DataFrame:
    """Shadow rows for one origin. `live` holds the live log rows for this origin (the HistGB rows are used)."""
    model = model or SolarWindShadow.load()
    ready = sw_archive.readiness(archive, origin)
    status = "no_sw" if not ready["today"] else ("full" if ready["echo"] else "no_echo")
    sw = sw_archive.daily_summary(archive)
    out = model.predict(daily, origin, sw)
    hist = live[live["model"] == "histgb"].set_index("lead").reindex(out["lead"])
    out["ap_live"], out["kpmax_live"] = hist["ap"].to_numpy(), hist["kpmax"].to_numpy()
    out["served"] = "histgb_fallback" if status == "no_sw" else NAME
    for t in config.FORECAST_TARGETS:
        out[t] = out[f"{t}_live"] if status == "no_sw" else out[f"{t}_sw"]
    out = out.assign(issued_at=issued_at, origin=origin, model_version=model.version, sw_status=status,
                     echo_days_missing=ready["echo_days_missing"])
    return out.reindex(columns=LOG_COLUMNS)


def load_log(path=None) -> pd.DataFrame:
    path = path or config.SHADOW_LOG
    if not path.exists():
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.read_csv(path, parse_dates=["issued_at", "origin", "target_date"])


def append(log: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Existing rows are never changed; an origin already logged is not issued again."""
    new = new[~new.set_index(KEY).index.isin(log.set_index(KEY).index)] if len(log) else new
    return pd.concat([log, new], ignore_index=True) if len(log) else new.reset_index(drop=True)


def train() -> SolarWindShadow:
    from src.daily import load_daily
    params, _ = gbm.load_params()
    daily = load_daily()
    window = backtest.training_rows(daily, pd.Timestamp(config.PRODUCTION_END) + pd.Timedelta(days=1))
    model = SolarWindShadow().fit(window, omni_daily(), params)
    model.save()
    print(f"saved {BUNDLE} ({model.version}, {len(model.columns_)} features)")
    return model


if __name__ == "__main__":
    from src.forecast import sw_shadow           # pickle the class under its module path, not __main__
    sw_shadow.train()
