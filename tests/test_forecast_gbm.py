"""Forecast features and the HistGB forecaster: values, causality, and the frozen production bundle."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.forecast import features as F
from src.forecast import gbm, registry


@pytest.fixture(scope="module")
def daily():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2008-01-01", "2012-12-31", freq="D", name="date")
    ap = rng.gamma(2, 6, len(idx)).round()
    return pd.DataFrame({"ap": ap, "kpmax": np.clip(1 + ap / 8, 0, 9), "f107_obs": rng.uniform(70, 200, len(idx)),
                         "gfz_flag": 2, "definitive": True}, index=idx)


@pytest.mark.parametrize("h", config.FORECAST_LEADS)
def test_features_use_only_the_past(daily, h):
    """Every feature at D is identical when all days after D are removed."""
    full = F.features(daily, h)
    for d in ["2010-03-03", "2011-08-19", "2012-12-31"]:
        cut = F.features(daily.loc[:d], h)
        pd.testing.assert_series_equal(full.loc[d], cut.loc[d])


def test_recurrence_and_target_alignment(daily):
    d, h = pd.Timestamp("2011-05-10"), 5
    X, y = F.features(daily, h), F.targets(daily, h)
    day = lambda k: daily.loc[d + pd.Timedelta(days=k), "ap"]           # noqa: E731
    assert X.loc[d, "ap_lag0"] == day(0) and X.loc[d, "ap_lag6"] == day(-6)
    assert X.loc[d, "ap_rec27"] == day(h - 27) and X.loc[d, "ap_rec81"] == day(h - 81)
    assert X.loc[d, "ap_rec27w"] == pytest.approx(np.mean([day(h - 28), day(h - 27), day(h - 26)]))
    assert y.loc[d, "ap"] == day(h)                                      # the label is the TARGET day's value
    target_day = d + pd.Timedelta(days=h)
    assert X.loc[d, "doy_sin"] == pytest.approx(np.sin(2 * np.pi * target_day.day_of_year / 365.25))


def test_frozen_bundle_is_not_refitted_and_predicts_the_same(daily, tmp_path):
    model = gbm.HistGBDirect(log_ap=True).fit(daily.loc[:"2011-12-31"])
    origins = pd.DatetimeIndex(["2012-06-01", "2012-09-30"])
    before = model.predict(daily, origins)
    path = tmp_path / "histgb.joblib"
    model.save(path)
    loaded = gbm.HistGBDirect.load(path)
    assert loaded.frozen
    loaded.fit(daily)                                    # the daily job calls fit(); a frozen bundle ignores it
    assert loaded.trained_until_ == "2011-12-31"
    pd.testing.assert_frame_equal(loaded.predict(daily, origins), before)
    assert (before["ap"] >= 0).all() and before["kpmax"].between(0, 9).all()


def test_production_models_include_histgb_only_when_a_bundle_exists(daily, tmp_path, monkeypatch):
    monkeypatch.setattr(gbm, "BUNDLE", tmp_path / "missing.joblib")
    assert "histgb" not in [m.name for m in registry.production_models()]
    gbm.HistGBDirect().fit(daily.loc[:"2011-12-31"]).save(tmp_path / "histgb.joblib")
    monkeypatch.setattr(gbm, "BUNDLE", tmp_path / "histgb.joblib")
    assert "histgb" in [m.name for m in registry.production_models()]


def test_committed_production_bundle_loads_and_matches_its_settings():
    """The bundle the daily job loads must unpickle outside the training script (the class must not be recorded
    under __main__) and use the committed tuned settings."""
    if not gbm.BUNDLE.exists():
        pytest.skip("no production bundle (HistGB did not pass its validation rule)")
    import sklearn
    model = gbm.HistGBDirect.load()
    assert type(model) is gbm.HistGBDirect and model.frozen
    assert len(model.models_) == len(config.FORECAST_LEADS) * len(config.FORECAST_TARGETS)
    params, log_ap = gbm.load_params()
    assert model.params == params and model.log_ap == log_ap
    import joblib
    assert joblib.load(gbm.BUNDLE)["sklearn_version"] == sklearn.__version__


def test_flare_spike_does_not_reach_the_f107_features(daily):
    """Regression (D-47): a flare-contaminated F10.7 day must be ignored, as the nowcaster already did."""
    spiked = daily.copy()
    day = pd.Timestamp("2011-03-07")
    spiked.loc[day, "f107_obs"] = 939.0                   # the real 2011-03-07 spike
    clean, dirty = F.features(daily.assign(f107_obs=daily["f107_obs"].mask(daily.index == day)), 1), F.features(spiked, 1)
    pd.testing.assert_series_equal(dirty["f107_mean81"], clean["f107_mean81"])
    assert dirty.loc[day, "f107"] == clean.loc[day, "f107"] < 300
