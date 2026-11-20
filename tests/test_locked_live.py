"""Locked model live parts (D-76): the image log is append-only and never blocks; the shadow picks the right
fallback and logs which model served each row."""
import numpy as np
import pandas as pd
import pytest

from src import backtest, config
from src.forecast import imagery, locked_shadow, sw_shadow
from src.ingest import aia_live, sw_archive

FEATS = {"ch_band_low": 5.0, "ch_band": 4.0, "ch_east": 3.0, "ch_disk": 2.0, "ch_dark": 0.3}


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    p = tmp_path / "imagery_daily.csv"
    monkeypatch.setattr(config, "IMAGERY_LOG", p)
    return p


def test_image_log_appends_and_keeps_first_values(log_path):
    now = pd.Timestamp("2026-11-20 01:00")
    aia_live.update(now=now, fetch=lambda day, folder: FEATS)
    out = aia_live.update(now=now + pd.Timedelta(days=1), fetch=lambda day, folder: {**FEATS, "ch_band_low": 9.0})
    assert out.loc["2026-11-20", "ch_band_low"] == 5.0          # unchanged
    assert out.loc["2026-11-21", "ch_band_low"] == 9.0          # new day added
    assert out.index.is_unique


def test_image_failure_only_warns(log_path):
    aia_live.update(now=pd.Timestamp("2026-11-20 01:00"), fetch=lambda day, folder: FEATS)
    before = log_path.read_bytes()

    def down(day, folder):
        raise ConnectionError("JSOC timed out")
    aia_live.update(now=pd.Timestamp("2026-11-25 01:00"), fetch=down)
    assert log_path.read_bytes() == before


def test_missing_image_returns_none():
    class R:
        status_code, content = 404, b"not found"
    assert aia_live.fetch_day(pd.Timestamp("2026-11-20"), None, get=lambda url, timeout: R()) is None


def test_near_real_time_marker_is_accepted():
    assert imagery.usable(0) and imagery.usable(imagery.NRT_FLAG)
    assert not imagery.usable(imagery.NRT_FLAG | 1) and not imagery.usable(4)


@pytest.fixture(scope="module")
def models():
    rng = np.random.default_rng(3)
    days = pd.date_range("2015-01-01", "2026-11-19", freq="D", name="date")
    ap = rng.gamma(2, 6, len(days)).round()
    daily = pd.DataFrame({"ap": ap, "kpmax": np.clip(1 + ap / 8, 0, 9), "f107_obs": rng.uniform(70, 200, len(days)),
                          "gfz_flag": 2, "definitive": True}, index=days)
    hours = pd.date_range("2015-01-01", "2026-11-19 23:00", freq="h", name="time")
    archive = pd.DataFrame({"speed": rng.uniform(300, 700, len(hours)), "bz_gsm": rng.normal(0, 3, len(hours)),
                            "by_gsm": rng.normal(0, 3, len(hours)), "density": 5.0, "b_scalar": 6.0}, index=hours)
    archive["omni_pressure"] = sw_archive.flow_pressure(archive["density"], archive["speed"])
    images = pd.DataFrame({k: rng.uniform(0, 10, len(days)) for k in imagery.COLUMNS}, index=days)
    small = {t: {"learning_rate": 0.1, "max_iter": 20, "max_leaf_nodes": 7, "min_samples_leaf": 20,
                 "l2_regularization": 0.0} for t in config.FORECAST_TARGETS}
    window = backtest.training_rows(daily, pd.Timestamp("2026-07-01"))
    sw = sw_archive.daily_summary(archive)
    locked = locked_shadow.LockedShadow().fit(window, sw, images, small)
    swm = sw_shadow.SolarWindShadow().fit(window, sw, small)
    return daily, archive, images, locked, swm


def _live(origin):
    return pd.DataFrame({"model": "histgb", "lead": list(config.FORECAST_LEADS), "ap": 11.0, "kpmax": 3.0, "origin": origin})


@pytest.mark.parametrize("case, served", [("full", locked_shadow.NAME), ("no_image", sw_shadow.NAME),
                                           ("no_sw", "histgb_fallback")])
def test_fallback_chain(models, case, served):
    daily, archive, images, locked, swm = models
    origin = pd.Timestamp("2026-11-18")
    if case == "no_image":
        images = images.loc[:"2026-11-16"]                     # no image on the issue day or the day before
    if case == "no_sw":
        archive = archive.loc[:"2026-11-16"]
    out = locked_shadow.issue(daily, origin, _live(origin), archive, images, pd.Timestamp("2026-11-19"), locked, swm)
    assert (out["status"] == case).all() and (out["served"] == served).all()
    src = {"full": "locked", "no_image": "sw", "no_sw": "live"}[case]
    assert (out["ap"] == out[f"ap_{src}"]).all()
