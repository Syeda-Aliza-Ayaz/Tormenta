"""Storm classifier (D-48): no future data, thresholds chosen for rare events, frozen production bundle."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.forecast import storm


@pytest.fixture(scope="module")
def daily():
    rng = np.random.default_rng(7)
    idx = pd.date_range("2006-01-01", "2012-12-31", freq="D", name="date")
    phase = np.sin(2 * np.pi * np.arange(len(idx)) / config.RECURRENCE_DAYS)
    kp = np.clip(3 + 1.5 * phase + rng.normal(0, 1, len(idx)), 0, 9)
    return pd.DataFrame({"ap": np.clip(4 * kp, 0, 400), "kpmax": kp, "f107_obs": rng.uniform(70, 200, len(idx)),
                         "gfz_flag": 2, "definitive": True}, index=idx)


@pytest.fixture(scope="module")
def model(daily):
    return storm.StormClassifier().fit(daily.loc[:"2010-12-31"])


def test_probabilities_use_only_the_past(model, daily):
    origins = pd.DatetimeIndex(["2011-04-01", "2012-08-20"])
    full = model.predict(daily, origins)
    for o in origins:
        pd.testing.assert_frame_equal(full[full["origin"] == o].reset_index(drop=True),
                                      model.predict(daily.loc[:o], [o]))
    assert full["storm_prob"].between(0, 1).all() and len(full) == 2 * len(config.FORECAST_LEADS)


def test_thresholds_maximise_heidke_skill():
    rng = np.random.default_rng(8)
    obs = rng.random(4000) < 0.1                                   # rare event, 10%
    prob = np.clip(0.08 + 0.3 * obs + rng.normal(0, 0.08, 4000), 0, 1)
    fc = pd.DataFrame({"lead": 1, "storm_prob": prob, "storm_obs": obs})
    t = storm.tune_thresholds(fc)[1]
    assert 0.1 < t < 0.4                                           # well below 0.5: a rare-event threshold


def test_frozen_bundle_keeps_thresholds(model, daily, tmp_path):
    model.thresholds_ = {h: 0.3 for h in config.FORECAST_LEADS}
    model.save(tmp_path / "s.joblib")
    loaded = storm.StormClassifier.load(tmp_path / "s.joblib")
    loaded.fit(daily)                                              # frozen: ignored
    assert loaded.frozen and loaded.thresholds_ == model.thresholds_ and loaded.trained_until_ == "2010-12-31"


def test_committed_bundle_loads():
    if not storm.BUNDLE.exists():
        pytest.skip("no storm bundle")
    m = storm.StormClassifier.load()
    assert type(m) is storm.StormClassifier and set(m.thresholds_) == set(config.FORECAST_LEADS)
