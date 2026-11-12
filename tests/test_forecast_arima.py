"""ARIMA family: the vectorised multi-origin forecast must equal statsmodels' own forecast, and use no future data."""
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("statsmodels")
from statsmodels.tsa.statespace.sarimax import SARIMAX  # noqa: E402

from src import config  # noqa: E402
from src.forecast import arima  # noqa: E402


@pytest.fixture(scope="module")
def daily():
    rng = np.random.default_rng(4)
    idx = pd.date_range("2009-01-01", "2012-12-31", freq="D", name="date")
    phase = np.sin(2 * np.pi * np.arange(len(idx)) / config.RECURRENCE_DAYS)
    ap = np.clip(10 + 6 * phase + rng.gamma(2, 3, len(idx)), 0, 400).round()
    return pd.DataFrame({"ap": ap, "kpmax": np.clip(1 + ap / 8, 0, 9), "f107_obs": rng.uniform(70, 200, len(idx)),
                         "gfz_flag": 2, "definitive": True}, index=idx)


@pytest.fixture(scope="module")
def fitted(daily):
    train = daily.loc[:"2011-12-31"]
    return {"arima": arima.StateSpaceForecaster("arima", (1, 0, 1)).fit(train),
            "arimax": arima.StateSpaceForecaster("arimax", (1, 0, 1), exog=True).fit(train)}


def _statsmodels_forecast(model, daily, origin, target):
    """Reference: statsmodels filters the series up to the origin with the fixed parameters and forecasts 7 days."""
    log = model._log(target)
    upto = daily.loc[:origin]
    y = arima._transform(upto[target], log)
    exog = future = None
    if model.exog:
        x = arima.exog_frame(upto, log)
        y = y.where(x.notna().all(axis=1))
        exog = x.fillna(0.0).to_numpy()
        days = [origin + pd.Timedelta(days=h) for h in config.FORECAST_LEADS]
        rec = arima._transform(daily["ap"], log).shift(config.RECURRENCE_DAYS).reindex(days).to_numpy()
        future = np.column_stack([rec, np.repeat(x["f107_mean81"].iloc[-1], len(days))])
    res = SARIMAX(y.to_numpy(), exog=exog, order=model.order, seasonal_order=model.seasonal_order,
                  trend="c").filter(model.params_[target])
    return np.clip(arima._inverse(res.forecast(len(config.FORECAST_LEADS), exog=future), log), 0,
                   arima.TARGET_MAX[target])


@pytest.mark.parametrize("name", ["arima", "arimax"])
@pytest.mark.parametrize("target", config.FORECAST_TARGETS)
def test_matches_statsmodels_forecast(fitted, daily, name, target):
    model = fitted[name]
    origins = pd.DatetimeIndex(["2012-03-14", "2012-10-02"])
    ours = model.predict(daily, origins)
    for origin in origins:
        got = ours[ours["origin"] == origin].sort_values("lead")[target].to_numpy()
        np.testing.assert_allclose(got, _statsmodels_forecast(model, daily, origin, target), rtol=1e-6, atol=1e-6)


def test_frozen_bundle_roundtrip(fitted, daily, tmp_path):
    model = fitted["arimax"]
    origins = pd.DatetimeIndex(["2012-06-01"])
    before = model.predict(daily, origins)
    model.save(tmp_path / "arimax.joblib")
    loaded = arima.StateSpaceForecaster.load(tmp_path / "arimax.joblib")
    loaded.fit(daily)                                      # frozen: ignored
    assert loaded.frozen and loaded.trained_until_ == "2011-12-31"
    pd.testing.assert_frame_equal(loaded.predict(daily, origins), before)
