"""Re-issue every 3 hours (D-72): an update sees only blocks and solar wind that have ended by its time."""
import numpy as np
import pandas as pd
import pytest

from src.forecast.experiments import intraday as I


@pytest.fixture
def blocks():
    rng = np.random.default_rng(5)
    days = pd.date_range("2016-01-01", periods=40, freq="D", name="date")
    return pd.DataFrame(rng.choice(np.arange(0, 9.01, 1 / 3), size=(40, 8)), index=days, columns=I.KP_COLS)


@pytest.fixture
def hourly():
    rng = np.random.default_rng(6)
    idx = pd.date_range("2016-01-01", periods=40 * 24, freq="h", name="time")
    h = pd.DataFrame({"speed": rng.uniform(300, 700, len(idx)), "bz_gsm": rng.normal(0, 4, len(idx))}, index=idx)
    h["vbs"] = h["speed"] * (-h["bz_gsm"]).clip(lower=0) / 1000
    return h


@pytest.mark.parametrize("k", I.UPDATES)
def test_blocks_after_the_update_change_nothing(blocks, k):
    before = I.block_features(blocks, k)
    later = blocks.copy()
    later.iloc[:, k:] = 9.0                                     # blocks not yet ended at update k
    pd.testing.assert_frame_equal(before, I.block_features(later, k))


@pytest.mark.parametrize("k", I.UPDATES)
def test_solar_wind_after_the_update_changes_nothing(hourly, k):
    before = I.solar_wind_features(hourly, k)
    later = hourly.copy()
    after = later.index.hour >= 3 * k
    later.loc[after, ["speed", "bz_gsm", "vbs"]] = [2000.0, -50.0, 100.0]
    pd.testing.assert_frame_equal(before, I.solar_wind_features(later, k))


def test_block_features_values(blocks):
    f = I.block_features(blocks, 3)
    row = blocks.iloc[0, :3].to_numpy()
    assert f["kp_sofar_max"].iloc[0] == pytest.approx(row.max())
    assert f["ap_sofar_mean"].iloc[0] == pytest.approx(I.kp_to_ap(row).mean())
    assert f["kp_last_change"].iloc[0] == pytest.approx(row[2] - row[1])
    assert (f["blocks_known"] == 3).all()


def test_kp_to_ap_table():
    assert I.kp_to_ap(np.array([0, 1 / 3, 1, 4.667, 9]).round(3)).tolist() == [0, 2, 4, 39, 400]


def test_design_uses_yesterday_as_issue_day():
    """Today's row carries the daily features of issue day D-1 (lead day 1 for today, 2 for tomorrow)."""
    from src.forecast import features as F
    rng = np.random.default_rng(3)
    days = pd.date_range("2015-01-01", "2016-03-01", freq="D", name="date")
    ap = rng.gamma(2, 6, len(days)).round()
    daily = pd.DataFrame({"ap": ap, "kpmax": np.clip(1 + ap / 8, 0, 9), "f107_obs": 120.0, "gfz_flag": 2,
                          "definitive": True}, index=days)
    blocks = pd.DataFrame(2.0, index=days, columns=I.KP_COLS)
    X = I.design(daily, blocks, pd.DataFrame(index=days), 4, 0)
    ref = F.features(daily, 1)
    d = pd.Timestamp("2016-02-10")
    assert X.loc[d, "ap_lag0"] == ref.loc[d - pd.Timedelta(days=1), "ap_lag0"] == daily.loc[d - pd.Timedelta(days=1), "ap"]
