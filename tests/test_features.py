"""Guards for the two silent failure modes: future leakage and gap-crossing lags."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.features import build_features, derived, kp_history_features, monotonic_cst, storm_memory

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
    # cuts at every position inside a 3-h Kp block (hours 5, 17, 21 → positions 2, 2, 0; 22 → 1)
    for cut in [hourly.index[30 * 24 + 5], hourly.index[90 * 24 + 17], hourly.index[60 * 24 + 21],
                hourly.index[61 * 24 + 22]]:
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


def test_todays_f107_features_do_not_need_todays_value(synthetic):
    """Live, today's flux (measured ~20 UT) is never known yet; today's features must not depend on it."""
    hourly, f107 = synthetic
    day = hourly.index[60 * 24].normalize()
    hours = hourly.loc[:day + pd.Timedelta("23h")]
    known = build_features(hours, f107.loc[:day])
    not_yet = build_features(hours, f107.loc[:day - pd.Timedelta("1D")])
    pd.testing.assert_frame_equal(known.loc[day:], not_yet.loc[day:])
    assert not_yet.loc[day:, ["f107_prev", "f107_mean81d"]].notna().all().all()


def test_no_geomagnetic_inputs_and_enough_features(synthetic):
    hourly, f107 = synthetic
    cols = build_features(hourly, f107).columns
    assert not [c for c in cols if c.split("_")[0].lower() in GEOMAGNETIC]
    assert len(cols) > 15


def test_block_so_far_ignores_later_hours_in_block(synthetic):
    """Changing the 3rd hour of a block must not change features at its 1st and 2nd hours."""
    hourly, f107 = synthetic
    t0 = hourly.index[50 * 24 + 9]                     # 09 UT = block start
    before = build_features(hourly, f107).loc[t0:t0 + pd.Timedelta("1h")]
    spiked = hourly.copy()
    spiked.loc[t0 + pd.Timedelta("2h"), ["bz_gsm", "speed"]] = [-50.0, 1500.0]
    after = build_features(spiked, f107).loc[t0:t0 + pd.Timedelta("1h")]
    pd.testing.assert_frame_equal(before, after)
    assert list(build_features(hourly, f107).loc[t0:t0 + pd.Timedelta("2h"), "block_hour"]) == [0, 1, 2]


def test_kp_history_ablation_uses_only_previous_blocks():
    """The ablation-only Kp features must not see the current block's Kp."""
    idx = pd.date_range("2020-01-01", periods=24 * 10, freq="h")
    kp = pd.Series(np.repeat(np.arange(len(idx) // 3) % 9, 3).astype(float), index=idx)
    base = kp_history_features(kp, idx)
    changed = kp.copy()
    t0 = idx[5 * 24 + 12]                              # a block start
    changed.loc[t0:t0 + pd.Timedelta("2h")] = 9.0      # alter the current block only
    after = kp_history_features(changed, idx)
    block = slice(t0, t0 + pd.Timedelta("2h"))
    pd.testing.assert_frame_equal(base.loc[block], after.loc[block])
    assert (base.loc[block, "kp_prev1"] == kp.loc[t0 - pd.Timedelta("3h")]).all()


def test_storm_memory_uses_only_fixed_trailing_window(synthetic):
    """Live serving only has a few days of data: storm memory must ignore anything older than its window."""
    hourly, _ = synthetic
    memory = lambda h: storm_memory(pd.concat([h, derived(h)], axis=1))
    t = hourly.index[80 * 24 + 7]
    old = hourly.copy()
    old.loc[:t - pd.Timedelta(hours=config.MEMORY_WINDOW_HOURS), ["bz_gsm", "speed"]] = [-40.0, 1200.0]
    pd.testing.assert_series_equal(memory(hourly).loc[t], memory(old).loc[t])
    assert config.MIN_HISTORY_HOURS >= config.MEMORY_WINDOW_HOURS


def test_monotonic_constraints_name_real_features(synthetic):
    hourly, f107 = synthetic
    cols = set(build_features(hourly, f107).columns)
    base = pd.concat([hourly, derived(hourly)], axis=1)
    cols |= set(storm_memory(base).columns)          # storm memory is switched off in production
    cst = monotonic_cst(cols)
    assert set(config.MONOTONIC_INCREASING + config.MONOTONIC_DECREASING) <= cols
    assert cst["newell"] == 1 and cst["bz_gsm"] == -1


def test_production_features_exclude_kp_history(synthetic):
    hourly, f107 = synthetic
    assert not {"kp_prev1", "kp_prev2", "kp_prev_mean24h"} & set(build_features(hourly, f107).columns)
