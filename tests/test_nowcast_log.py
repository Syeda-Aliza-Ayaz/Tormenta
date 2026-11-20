"""Hourly nowcast log: append-only, completed hours only, a failure never touches the file."""
import pandas as pd
import pytest

from src import config, nowcast_log


def pred(start, hours, kp=2.0, ahead_last=True):
    idx = pd.date_range(start, periods=hours, freq="h", name="time")
    df = pd.DataFrame({"kp_pred": kp, "kp_lo": kp - 1, "kp_hi": kp + 1, "ahead": False}, index=idx)
    if ahead_last:
        df.iloc[-1, df.columns.get_loc("ahead")] = True
    return df


@pytest.fixture
def path(tmp_path, monkeypatch):
    p = tmp_path / "nowcast_log.csv"
    monkeypatch.setattr(config, "NOWCAST_LOG", p)
    return p


def test_only_completed_hours_are_logged(path):
    now = pd.Timestamp("2026-11-20 10:40")
    out = nowcast_log.update(run=lambda: (pred("2026-11-20 05:00", 7), "2019-12-31"), now=now)
    assert out.index.max() == pd.Timestamp("2026-11-20 09:00")           # 10:00 in progress, 11:00 ahead
    assert (out["model_trained_until"] == "2019-12-31").all()


def test_first_value_is_kept(path):
    now = pd.Timestamp("2026-11-20 10:40")
    nowcast_log.update(run=lambda: (pred("2026-11-20 05:00", 7, kp=2.0), "x"), now=now)
    later = pd.Timestamp("2026-11-20 14:10")
    out = nowcast_log.update(run=lambda: (pred("2026-11-20 05:00", 11, kp=5.0), "x"), now=later)
    assert out.loc["2026-11-20 06:00", "kp_pred"] == 2.0                  # unchanged
    assert out.loc["2026-11-20 12:00", "kp_pred"] == 5.0                  # new hour added
    assert out.index.is_unique and len(out) == 9                          # 05:00 … 13:00


def test_failure_leaves_the_file_alone(path):
    nowcast_log.update(run=lambda: (pred("2026-11-20 05:00", 5), "x"), now=pd.Timestamp("2026-11-20 12:00"))
    before = path.read_bytes()

    def down():
        raise ConnectionError("NOAA timed out")
    nowcast_log.update(run=down, now=pd.Timestamp("2026-11-20 15:00"))
    assert path.read_bytes() == before
