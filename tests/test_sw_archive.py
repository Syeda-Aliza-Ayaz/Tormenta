"""Solar-wind archive: keeps the live feed past 7 days, never erases data, shares the training feature definition."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.ingest import sw_archive


def live_hours(start, hours, speed=400.0, missing=()):
    idx = pd.date_range(start, periods=hours, freq="h", name="time")
    df = pd.DataFrame({"speed": speed, "bz_gsm": -2.0, "by_gsm": 1.0, "density": 5.0, "b_scalar": 6.0,
                       "bx": 0.0, "temperature": 1e5}, index=idx)
    df.loc[df.index.isin(pd.DatetimeIndex(missing)), ["speed", "density"]] = np.nan
    return df


@pytest.fixture
def path(tmp_path, monkeypatch):
    p = tmp_path / "solar_wind_hourly.csv"
    monkeypatch.setattr(config, "SOLAR_WIND_ARCHIVE", p)
    return p


def test_archive_grows_past_the_feed_window(path):
    now = pd.Timestamp("2026-11-20 01:30")
    sw_archive.update(fetch=lambda: live_hours("2026-11-13", 7 * 24), now=now)
    later = pd.Timestamp("2026-11-27 01:30")
    out = sw_archive.update(fetch=lambda: live_hours("2026-11-20", 7 * 24), now=later)
    assert out.index.min() == pd.Timestamp("2026-11-13") and out.index.is_unique
    assert len(sw_archive.load(path)) == 14 * 24


def test_current_hour_is_not_stored(path):
    out = sw_archive.update(fetch=lambda: live_hours("2026-11-19 20:00", 6), now=pd.Timestamp("2026-11-19 23:10"))
    assert out.index.max() == pd.Timestamp("2026-11-19 22:00")


def test_later_fetch_fills_gaps_but_never_erases(path):
    now = pd.Timestamp("2026-11-21")
    gap = pd.Timestamp("2026-11-19 05:00")
    sw_archive.update(fetch=lambda: live_hours("2026-11-19", 24, missing=[gap]), now=now)
    out = sw_archive.update(fetch=lambda: live_hours("2026-11-19", 24, speed=500.0), now=now)
    assert out.loc[gap, "speed"] == 500.0                                  # the gap is filled
    assert out.loc[pd.Timestamp("2026-11-19 06:00"), "speed"] == 400.0     # complete hours keep their first value
    worse = live_hours("2026-11-19", 24, missing=pd.date_range("2026-11-19", periods=24, freq="h"))
    out = sw_archive.update(fetch=lambda: worse, now=now)
    assert out["speed"].notna().all()


def test_fetch_failure_leaves_archive_alone(path):
    sw_archive.update(fetch=lambda: live_hours("2026-11-19", 24), now=pd.Timestamp("2026-11-21"))
    before = path.read_bytes()

    def down():
        raise ConnectionError("timed out")
    sw_archive.update(fetch=down, now=pd.Timestamp("2026-11-22"))
    assert path.read_bytes() == before


def test_pressure_matches_omni_definition():
    out = sw_archive.from_live(live_hours("2026-11-19", 1), pd.Timestamp("2026-11-20"))
    assert out["omni_pressure"].iloc[0] == pytest.approx(2e-6 * 5.0 * 400.0 ** 2)


def test_daily_summary_blanks_thin_days():
    h = sw_archive.from_live(live_hours("2026-11-18", 48, missing=pd.date_range("2026-11-19", periods=13, freq="h")),
                             pd.Timestamp("2026-11-21"))
    d = sw_archive.daily_summary(h)
    assert d.loc["2026-11-18", "sw_speed"] == 400.0 and d.loc["2026-11-18", "sw_vbs"] == pytest.approx(0.8)
    assert d.loc["2026-11-19"].isna().all()                                # 11 hours < 12


def test_readiness_counts_echo_days():
    h = sw_archive.from_live(live_hours("2026-10-01", 50 * 24), pd.Timestamp("2026-11-21"))
    origin = pd.Timestamp("2026-11-19")
    assert sw_archive.readiness(h, origin)["echo"]
    short = h.loc["2026-10-27":]
    r = sw_archive.readiness(short, origin)
    assert r["today"] and not r["echo"] and r["echo_days_missing"] == 4    # days 24-27 back are missing
