"""ARIMA, SARIMA (27-day season) and ARIMAX (PLAN.md §6), as state-space models from statsmodels.

How a rolling backtest stays fast and honest (DECISIONS D-10):
  * the parameters are estimated ONCE, on the training years (fit);
  * forecasting runs the Kalman filter over the daily series with those parameters FIXED, always from the same
    start day (the first day of the series given), so the state at day D depends only on days ≤ D;
  * the 7-day forecast from each origin is projected from the filtered state at D:
        a(t+1) = T·a(t) + c,   y(t+h) = Z·a(t+h) + d(t+h)
    for all origins at once. tests/test_forecast_arima.py checks it against statsmodels' own forecast.

ARIMAX inputs (never future values, DECISIONS D-09):
  ap_rec27      Ap 27 days before the TARGET day: already observed when the forecast is made (h ≤ 7 < 27)
  f107_mean81   81-day trailing F10.7 mean: the value at D is carried forward over the forecast days

    python -m src.forecast.arima      # select orders on train, validation backtest, rule, save bundles
"""
import json
import warnings

import joblib
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from src import config
from src.forecast.base import Forecaster, as_origins, stack

BUNDLE_DIR = config.MODELS_DIR / "forecast"
SETTINGS_JSON = BUNDLE_DIR / "arima_settings.json"
TARGET_MAX = {"ap": 400.0, "kpmax": 9.0}


def _transform(y: pd.Series, log: bool) -> pd.Series:
    return np.log1p(y) if log else y


def _inverse(y: np.ndarray, log: bool) -> np.ndarray:
    return np.expm1(y) if log else y


def exog_frame(daily: pd.DataFrame, log: bool) -> pd.DataFrame:
    """ARIMAX regressors as they are known ON each day t (used for the in-sample filter)."""
    f107 = daily["f107_obs"].rolling(config.F107_TRAILING_DAYS, min_periods=40).mean()
    return pd.DataFrame({"ap_rec27": _transform(daily["ap"], log).shift(config.RECURRENCE_DAYS),
                         "f107_mean81": f107.ffill()}, index=daily.index)


class StateSpaceForecaster(Forecaster):
    """One SARIMAX per target, parameters fixed after fit()."""

    def __init__(self, name: str, order=(2, 0, 1), seasonal_order=(0, 0, 0, 0), exog: bool = False,
                 log_ap: bool = True):
        self.name = name
        self.order, self.seasonal_order = tuple(order), tuple(seasonal_order)
        self.exog, self.log_ap = exog, log_ap
        self.frozen = False

    def _log(self, target):
        return self.log_ap and target == "ap"

    def _model(self, daily: pd.DataFrame, target: str) -> SARIMAX:
        log = self._log(target)
        y = _transform(daily[target], log)
        x = None
        if self.exog:
            x = exog_frame(daily, log)
            # the first weeks of a series have no regressors yet: treat those days as unobserved (y = NaN, the
            # Kalman filter skips them) instead of filling x from later days
            y = y.where(x.notna().all(axis=1))
            x = x.fillna(0.0)
        return SARIMAX(y.to_numpy(), exog=None if x is None else x.to_numpy(), order=self.order,
                       seasonal_order=self.seasonal_order, trend="c")

    def fit(self, daily):
        if self.frozen:
            return self
        self.params_ = {}
        for t in config.FORECAST_TARGETS:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")              # convergence chatter; checked via AIC and backtest
                res = self._model(daily, t).fit(disp=False, maxiter=200)
            self.params_[t] = res.params
            self.aic_ = getattr(self, "aic_", {}) | {t: float(res.aic)}
        self.trained_until_ = str(daily.index.max().date())
        return self

    def _forecast_target(self, daily: pd.DataFrame, origins: pd.DatetimeIndex, target: str) -> dict:
        log = self._log(target)
        series = daily.loc[: origins.max()]                   # nothing after the last origin enters the filter
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fr = self._model(series, target).filter(self.params_[target]).filter_results
        pos = series.index.get_indexer(origins)
        T = fr.transition[:, :, 0]
        c = fr.state_intercept[:, 0]
        Z = fr.design[:, :, 0]
        state = fr.filtered_state[:, pos]                     # a(D | data ≤ D), one column per origin
        if self.exog:
            beta = self.params_[target][1:3]                  # SARIMAX params: [const, exog..., ar..., ma..., σ²]
            ap_t = _transform(series["ap"], log)
            f107 = exog_frame(series, log)["f107_mean81"].to_numpy()[pos]
        out = {}
        for h in config.FORECAST_LEADS:
            state = T @ state + c[:, None]
            y = (Z @ state).ravel()
            if self.exog:
                rec = ap_t.shift(config.RECURRENCE_DAYS - h).to_numpy()[pos]   # Ap on D+h−27: already observed
                y = y + beta[0] * rec + beta[1] * f107
            out[h] = np.clip(_inverse(y, log), 0, TARGET_MAX[target])
        return out

    def predict(self, daily, origins):
        origins = as_origins(daily, origins)
        per_target = {t: self._forecast_target(daily, origins, t) for t in config.FORECAST_TARGETS}
        return stack(origins, {h: {t: per_target[t][h] for t in config.FORECAST_TARGETS}
                               for h in config.FORECAST_LEADS})

    def save(self, path=None, **meta):
        path = path or BUNDLE_DIR / f"{self.name}.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self, **meta}, path)

    @staticmethod
    def load(path) -> "StateSpaceForecaster":
        model = joblib.load(path)["model"]
        model.frozen = True
        return model


def default_models(settings: dict = None) -> list:
    """The three models with their selected settings (or sensible defaults before selection)."""
    s = settings or {"order": [2, 0, 1], "seasonal_order": [1, 0, 1, 27], "log_ap": True}
    return [StateSpaceForecaster("arima", s["order"], log_ap=s["log_ap"]),
            StateSpaceForecaster("sarima", s["order"], s["seasonal_order"], log_ap=s["log_ap"]),
            StateSpaceForecaster("arimax", s["order"], exog=True, log_ap=s["log_ap"])]


def load_settings(path=None):
    path = path or SETTINGS_JSON
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# ── Day-4 run: select on train → validation backtest → rule → production bundles ────────────────────────────
ORDER_GRID = [(p, d, q) for p in (1, 2, 3) for d in (0, 1) for q in (0, 1, 2)]
SEASONAL_GRID = [(1, 0, 0, 27), (1, 0, 1, 27)]
INNER_SPLIT = "2013-12-31"          # inside the training years: fit ≤ 2013, check 2014–2016


def _aic(daily, target, order, seasonal=(0, 0, 0, 0), log=True) -> float:
    m = StateSpaceForecaster("tmp", order, seasonal, log_ap=log)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(m._model(daily, target).fit(disp=False, maxiter=200).aic)


def select(train: pd.DataFrame) -> dict:
    """Orders by AIC on log(1+Ap) over the training years; then raw vs log Ap by RMSE on 2014–2016 (still train)."""
    from src import backtest, scorecard
    inner = train.loc[:INNER_SPLIT]
    aics = {order: _aic(inner, "ap", order) for order in ORDER_GRID}
    order = min(aics, key=aics.get)
    print("ARIMA order by AIC:", order, {str(k): round(v) for k, v in sorted(aics.items(), key=lambda kv: kv[1])[:4]})
    s_aics = {s: _aic(inner, "ap", order, s) for s in SEASONAL_GRID}
    seasonal = min(s_aics, key=s_aics.get)
    print("seasonal order by AIC:", seasonal, {str(k): round(v) for k, v in s_aics.items()})
    first, last = pd.Timestamp(INNER_SPLIT) + pd.Timedelta(days=1), train.index.max()
    rmse = {}
    for log in (False, True):
        fc = backtest.run([StateSpaceForecaster("arima", order, log_ap=log)], train, first, last)
        t = scorecard.lead_table(fc, references=())
        rmse[log] = float(t[t["target"] == "ap"]["rmse"].mean())
    print(f"Ap target on 2014-2016: raw RMSE {rmse[False]:.3f}, log RMSE {rmse[True]:.3f}")
    return {"order": list(order), "seasonal_order": list(seasonal), "log_ap": bool(rmse[True] < rmse[False]),
            "aic_order": {str(k): v for k, v in aics.items()}, "aic_seasonal": {str(k): v for k, v in s_aics.items()},
            "inner_rmse": {"raw": rmse[False], "log": rmse[True]}}


def main(reselect: bool = True) -> dict:
    from src import backtest, scorecard
    from src.daily import load_daily
    from src.forecast import registry
    from src.issue import production_window

    daily = load_daily()
    first, last = backtest.period("validation", daily)
    train = backtest.training_rows(daily, first)
    settings = load_settings()
    if reselect or not settings:
        settings = select(train)
        BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_JSON.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    # every model (baselines, HistGB, ARIMA family) + NOAA on the validation years
    fc = backtest.run(registry.all_models(), daily, first, last)
    fc = pd.concat([fc, backtest.noaa_rows(daily, first, last)], ignore_index=True)
    leads, storms = scorecard.lead_table(fc), scorecard.storm_table(fc)
    out = config.FORECAST_REPORTS_DIR / "metrics"
    leads.to_csv(out / "validation_leads.csv", index=False)
    storms.to_csv(out / "validation_storms.csv", index=False)

    # the same rule as HistGB, fixed in advance (DECISIONS D-31): mean Ap skill vs trailing27 over lead days > 0
    results = {}
    prod_rows = production_window(daily)
    for model in default_models(settings):
        ap = leads[(leads["model"] == model.name) & (leads["target"] == "ap")]
        skill = float(ap["skill_vs_trailing27"].mean())
        passed = skill > 0
        results[model.name] = skill
        print(f"{model.name}: mean Ap skill vs trailing27 = {skill:+.3f} -> {'PASS' if passed else 'FAIL'}")
        path = BUNDLE_DIR / f"{model.name}.joblib"
        if passed:
            model.fit(prod_rows).save(path, validation_skill_vs_trailing27=skill, settings=settings)
        elif path.exists():
            path.unlink()
    return {"leads": leads, "storms": storms, "skill": results, "settings": settings}


if __name__ == "__main__":
    import argparse
    from src.forecast import arima as _module      # pickle the class as src.forecast.arima, not __main__ (D-32)
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse-settings", action="store_true", help="skip order selection")
    _module.main(reselect=not ap.parse_args().reuse_settings)
