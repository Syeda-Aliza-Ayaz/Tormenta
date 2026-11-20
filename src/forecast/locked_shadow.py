"""The locked model (DECISIONS D-76) in shadow mode: logged next to the live model, not shown.

Model: HistGB + solar wind + 27-day echo + coronal holes, Poisson loss, live settings, the same inputs as the
validated variant `sw_rec_poisson_imagery`. Fitted on definitive days up to PRODUCTION_END, with OMNI solar wind
and archive image features for training; live inputs come from the solar-wind archive (sw_archive) and the
near-real-time image log (aia_live).

Fallbacks (D-76), stated on every row in `served`:
  no solar wind on the issue day          → the live HistGB forecast
  no usable image on the issue day or the day before → the solar-wind model (sw_shadow)
  otherwise                               → the locked model

  models/forecast/locked_shadow.joblib   the fitted model (refitted only by `python -m src.forecast.locked_shadow`)
  forecasts/locked_shadow_log.csv        APPEND-ONLY, one row per origin × lead day
"""
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from src import backtest, config
from src.forecast import features as F, gbm, imagery, storm, sw_shadow
from src.ingest import aia_live, sw_archive

BUNDLE = config.MODELS_DIR / "forecast" / "locked_shadow.joblib"
NAME = "histgb_sw_ch"
LOG_COLUMNS = ["issued_at", "origin", "model_version", "lead", "target_date", "status", "ap_locked", "kpmax_locked",
               "storm_prob_locked", "ap_sw", "kpmax_sw", "ap_live", "kpmax_live", "served", "ap", "kpmax"]


def ch_features(index: pd.DatetimeIndex, ch: pd.DataFrame) -> pd.DataFrame:
    """Coronal-hole inputs per issue day, the same definitions as validate_yearly.SolarWindRecPoissonImagery."""
    ch = ch.reindex(index)
    return pd.DataFrame({
        "ch_band_low": ch["ch_band_low"], "ch_band_low_lag1": ch["ch_band_low"].shift(1),
        "ch_band_low_lag2": ch["ch_band_low"].shift(2),
        "ch_band_low_change": ch["ch_band_low"] - ch["ch_band_low"].shift(1),
        "ch_east": ch["ch_east"], "ch_disk": ch["ch_disk"], "ch_dark": ch["ch_dark"]}, index=index)


def locked_features(daily: pd.DataFrame, h: int, sw: pd.DataFrame, ch: pd.DataFrame) -> pd.DataFrame:
    x = sw_shadow.sw_features(daily, h, sw)
    return x.join(ch_features(x.index, ch))


class LockedShadow:
    name = NAME

    def fit(self, daily, sw, ch, params) -> "LockedShadow":
        self.models_, self.classifiers_ = {}, {}
        for h in config.FORECAST_LEADS:
            X = locked_features(daily, h, sw, ch)
            tgt = F.targets(daily, h)
            rows = X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1) & ~daily["lead_in"]
            for t in config.FORECAST_TARGETS:
                k = rows & tgt[t].notna()
                self.models_[(h, t)] = gbm._model({**params[t], **sw_shadow.LOSS}).fit(X[k], tgt.loc[k, t])
            k = rows & tgt["kpmax"].notna()
            self.classifiers_[h] = HistGradientBoostingClassifier(
                **storm.PARAMS, early_stopping=False, random_state=config.RANDOM_STATE
            ).fit(X[k], (tgt.loc[k, "kpmax"] >= config.STORM_THRESHOLD).astype(int))
        self.columns_ = list(X.columns)
        self.trained_until_ = str(daily.index.max().date())
        self.version = f"{NAME}-{self.trained_until_}"
        return self

    def predict(self, daily, origin, sw, ch) -> pd.DataFrame:
        window = daily.loc[origin - pd.Timedelta(days=config.FORECAST_HISTORY_DAYS): origin]
        rows = []
        for h in config.FORECAST_LEADS:
            X = locked_features(window, h, sw, ch).loc[[origin], self.columns_]
            rows.append({"lead": h, "target_date": origin + pd.Timedelta(days=h),
                         "ap_locked": float(np.clip(self.models_[(h, "ap")].predict(X)[0], 0, 400)),
                         "kpmax_locked": float(np.clip(self.models_[(h, "kpmax")].predict(X)[0], 0, 9)),
                         "storm_prob_locked": float(self.classifiers_[h].predict_proba(X)[0, 1])})
        return pd.DataFrame(rows)

    def save(self, path=None):
        path = path or BUNDLE
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self, "sklearn_version": sklearn.__version__}, path)

    @staticmethod
    def load(path=None) -> "LockedShadow":
        return joblib.load(path or BUNDLE)["model"]


def status(archive: pd.DataFrame, images: pd.DataFrame, origin: pd.Timestamp) -> str:
    if not sw_archive.readiness(archive, origin)["today"]:
        return "no_sw"
    have = images.dropna(subset=["ch_band_low"]).index if len(images) else pd.DatetimeIndex([])
    if origin not in have and (origin - pd.Timedelta(days=1)) not in have:
        return "no_image"
    return "full"


def issue(daily, origin, live, archive, images, issued_at, model: LockedShadow = None,
          sw_model: sw_shadow.SolarWindShadow = None) -> pd.DataFrame:
    """Rows for one origin. `live` holds the live log rows for this origin; `images` is the image log."""
    model = model or LockedShadow.load()
    sw_model = sw_model or sw_shadow.SolarWindShadow.load()
    st = status(archive, images, origin)
    sw = sw_archive.daily_summary(archive)
    ch = images.reindex(columns=imagery.COLUMNS).astype(float) if len(images) else pd.DataFrame(columns=imagery.COLUMNS)
    out = model.predict(daily, origin, sw, ch)
    swp = sw_model.predict(daily, origin, sw)
    out["ap_sw"], out["kpmax_sw"] = swp["ap_sw"].to_numpy(), swp["kpmax_sw"].to_numpy()
    hist = live[live["model"] == "histgb"].set_index("lead").reindex(out["lead"])
    out["ap_live"], out["kpmax_live"] = hist["ap"].to_numpy(), hist["kpmax"].to_numpy()
    source = {"full": ("locked", NAME), "no_image": ("sw", sw_shadow.NAME), "no_sw": ("live", "histgb_fallback")}[st]
    out["served"] = source[1]
    for t in config.FORECAST_TARGETS:
        out[t] = out[f"{t}_{source[0]}"]
    out = out.assign(issued_at=issued_at, origin=origin, model_version=model.version, status=st)
    return out.reindex(columns=LOG_COLUMNS)


def load_log(path=None) -> pd.DataFrame:
    path = path or config.LOCKED_SHADOW_LOG
    if not path.exists():
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.read_csv(path, parse_dates=["issued_at", "origin", "target_date"])


def append(log: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    return sw_shadow.append(log, new)


def train() -> LockedShadow:
    """Production fit (after the one-time test, D-76): definitive days to PRODUCTION_END, images included."""
    from src.daily import load_daily
    params, _ = gbm.load_params()
    daily = load_daily()
    window = backtest.training_rows(daily, pd.Timestamp(config.PRODUCTION_END) + pd.Timedelta(days=1))
    ch = imagery.load()
    assert ch.index.max() >= pd.Timestamp(config.PRODUCTION_END) - pd.Timedelta(days=10), \
        "image features must reach PRODUCTION_END (python -m src.forecast.imagery --last <date>)"
    model = LockedShadow().fit(window, sw_shadow.omni_daily(), ch, params)
    model.save()
    print(f"saved {BUNDLE} ({model.version}, {len(model.columns_)} features)")
    return model


if __name__ == "__main__":
    from src.forecast import locked_shadow     # pickle the class under its module path, not __main__
    locked_shadow.train()
