"""D-75: Holt-Winters forecasts and recurrent-network inputs for issue day D do not depend on data after D."""
import numpy as np
import pandas as pd
import pytest

from src.forecast.experiments import report_models as R


@pytest.fixture
def series():
    rng = np.random.default_rng(4)
    idx = pd.date_range("2000-01-01", "2011-12-31", freq="D")
    t = np.arange(len(idx))
    return pd.Series(10 + 5 * np.sin(2 * np.pi * t / 27) + rng.gamma(2, 2, len(idx)), index=idx)


def test_holt_winters_uses_only_the_past(series):
    d = pd.Timestamp("2011-06-15")
    before = R.hw_forecasts(series, 2011, "ap")
    later = series.copy()
    later.loc[later.index > d] = 400.0
    after = R.hw_forecasts(later, 2011, "ap")
    keep = lambda f: f[f["origin"] <= d].reset_index(drop=True)  # noqa: E731
    pd.testing.assert_frame_equal(keep(before), keep(after))


def test_holt_winters_follows_the_season(series):
    """On a clean 27-day sine the 27-day-season model should beat a flat forecast clearly."""
    clean = series * 0 + 10 + 5 * np.sin(2 * np.pi * np.arange(len(series)) / 27)
    f = R.hw_forecasts(clean, 2011, "ap")
    f = f[f["origin"] >= "2011-01-01"]
    truth = clean.reindex(f["origin"] + pd.to_timedelta(f["lead"], unit="D")).to_numpy()
    ok = ~np.isnan(truth)                                             # targets past the series end are blank
    assert np.sqrt(np.mean((f["ap"].to_numpy()[ok] - truth[ok]) ** 2)) < 0.5


def test_rnn_inputs_end_at_the_issue_day():
    idx = pd.date_range("2000-01-01", periods=300, freq="D")
    hist = pd.DataFrame({"ap": np.arange(300.0), "kpmax": 1.0, "f107_obs": 100.0}, index=idx)
    d = idx[200]
    x = R.sequences(hist, pd.DatetimeIndex([d]))
    assert x.shape == (1, R.WINDOW, 5)
    assert x[0, -1, 0] == pytest.approx(200 / R.SCALE["ap"])          # last row is the issue day itself
    later = hist.copy()
    later.loc[later.index > d, :] = 999.0
    np.testing.assert_array_equal(x, R.sequences(later, pd.DatetimeIndex([d])))


def test_rnn_targets_are_the_following_days():
    idx = pd.date_range("2000-01-01", periods=40, freq="D")
    daily = pd.DataFrame({"ap": np.arange(40.0), "kpmax": np.arange(40.0) / 10, "definitive": True}, index=idx)
    y = R.targets(daily, pd.DatetimeIndex([idx[10]]))
    assert y[0, 0] == pytest.approx(11 / R.SCALE["ap"]) and y[0, 6] == pytest.approx(17 / R.SCALE["ap"])
    assert y[0, 7] == pytest.approx(1.1 / R.SCALE["kpmax"])
