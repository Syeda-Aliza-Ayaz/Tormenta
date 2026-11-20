"""D-73: 'how the issue day ended' uses only the issue day and earlier days."""
import numpy as np
import pandas as pd
import pytest

from src.forecast import validate_yearly as V


@pytest.fixture
def setup(monkeypatch):
    rng = np.random.default_rng(9)
    days = pd.date_range("2016-01-01", periods=60, freq="D", name="date")
    kp = pd.DataFrame(rng.choice(np.arange(0, 9.01, 1 / 3), size=(60, 8)).round(3), index=days,
                      columns=[f"kp{i}" for i in range(1, 9)])
    daily = pd.DataFrame({"kpmax": kp.max(axis=1), "ap": 10.0}, index=days)
    monkeypatch.setattr("src.ingest.fetch_gfz.load_gfz_daily", lambda: kp)
    return daily, kp


def test_values(setup):
    daily, kp = setup
    f = V.progress_features(daily)
    d = daily.index[20]
    assert f.loc[d, "kp_last_block"] == kp.loc[d, "kp8"]
    assert f.loc[d, "kp_max_last4"] == kp.loc[d, ["kp5", "kp6", "kp7", "kp8"]].max()
    assert f.loc[d, "storm_blocks"] == (kp.loc[d] >= 4.5).sum()
    assert f.loc[d, "kp_change_last4"] == pytest.approx(kp.loc[d, "kp8"] - kp.loc[d, "kp5"])


def test_storm_days_in_row():
    days = pd.date_range("2016-01-01", periods=6, freq="D", name="date")
    kp = pd.DataFrame(1.0, index=days, columns=[f"kp{i}" for i in range(1, 9)])
    kpmax = pd.Series([1, 5, 6, 1, 5, 5], index=days, dtype=float)
    import src.ingest.fetch_gfz as g
    orig = g.load_gfz_daily
    g.load_gfz_daily = lambda: kp
    try:
        f = V.progress_features(pd.DataFrame({"kpmax": kpmax}, index=days))
    finally:
        g.load_gfz_daily = orig
    assert f["storm_days_in_row"].tolist() == [0, 1, 2, 0, 1, 2]


def test_later_days_change_nothing(setup):
    daily, kp = setup
    cut = daily.index[30]
    before = V.progress_features(daily).loc[:cut]
    kp.loc[kp.index > cut] = 9.0
    daily.loc[daily.index > cut, "kpmax"] = 9.0
    after = V.progress_features(daily).loc[:cut]
    pd.testing.assert_frame_equal(before, after)
