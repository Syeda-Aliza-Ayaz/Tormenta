"""Guards for the two silent failure modes: future leakage and gap-crossing lags."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.features import build_features

GEOMAGNETIC = ("kp", "ap", "dst", "ae", "al", "au", "pcn")


@pytest.fixture
def synthetic():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2020-01-01", periods=24 * 120, freq="h")
    hourly = pd.DataFrame({
        "b_scalar": rng.uniform(2, 20, len(idx)),
        "bx": rng.normal(0, 3, len(idx)),
        "by_gsm": rng.normal(0, 3, len(idx)),
        "bz_gsm": rng.normal(0, 4, len(idx)),
        "temperature": rng.uniform(2e4, 3e5, len(idx)),
        "density": rng.uniform(1, 20, len(idx)),
        "speed": rng.uniform(300, 800, len(idx)),
    }, index=idx)
    hourly.iloc[rng.choice(len(idx), 200, replace=False), 3] = np.nan   # scattered gaps
    days = pd.date_range("2019-09-01", "2020-05-01", freq="D")
    f107 = pd.Series(rng.uniform(70, 200, len(days)), index=days)
    f107.iloc[150] = 900.0                                                # flare spike
    return hourly, f107


def test_causal(synthetic):
    """Features at t must not change when rows after t are appended."""
    hourly, f107 = synthetic
    full = build_features(hourly, f107)
    for cut in [hourly.index[30 * 24 + 5], hourly.index[90 * 24 + 17]]:
        part = build_features(hourly.loc[:cut], f107.loc[:cut.normalize()])
        pd.testing.assert_frame_equal(full.loc[:cut], part)


def test_complete_grid_lags(synthetic):
    """Dropped rows become NaN rows, so a 3-h lag is always exactly 3 hours."""
    hourly, f107 = synthetic
    holey = hourly.drop(hourly.index[500:510])
    feats = build_features(holey, f107)
    assert (feats.index.to_series().diff().dropna() == pd.Timedelta("1h")).all()
    t = hourly.index[520]
    assert feats.loc[t, "speed_lag3h"] == hourly.loc[t - pd.Timedelta("3h"), "speed"]
    assert np.isnan(feats.loc[hourly.index[512], "speed_lag3h"])


def test_f107_spike_removed_and_lagged(synthetic):
    hourly, f107 = synthetic
    feats = build_features(hourly, f107)
    spike_day = f107.index[150]
    next_day = feats.loc[spike_day + pd.Timedelta("1D"):].iloc[0]
    assert next_day["f107_prev"] < 300
    assert feats["f107_prev"].max() < 300


def test_no_geomagnetic_inputs_and_enough_features(synthetic):
    hourly, f107 = synthetic
    cols = build_features(hourly, f107).columns
    assert not [c for c in cols if c.split("_")[0].lower() in GEOMAGNETIC]
    assert len(cols) > 15
