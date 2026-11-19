"""Solar-wind shadow model: same features as the validated variant, fallback to the live model, append-only log."""
import numpy as np
import pandas as pd
import pytest

from src import backtest, config
from src.forecast import sw_shadow
from src.ingest import sw_archive

SMALL = {"learning_rate": 0.1, "max_iter": 20, "max_leaf_nodes": 7, "min_samples_leaf": 20, "l2_regularization": 0.0}


@pytest.fixture(scope="module")
def setup():
    rng = np.random.default_rng(3)
    days = pd.date_range("2018-01-01", "2026-11-19", freq="D", name="date")
    daily = pd.DataFrame({"ap": rng.gamma(2, 6, len(days)), "kpmax": rng.uniform(0, 7, len(days)),
                          "f107_obs": 120.0, "definitive": True, "gfz_flag": 2}, index=days)
    for c in [c for c in pd.read_csv(config.ROOT / "tests" / "data" / "daily_columns.txt", header=None)[0]] \
            if (config.ROOT / "tests" / "data" / "daily_columns.txt").exists() else []:
        daily.setdefault(c, 0.0)
    hours = pd.date_range("2025-01-01", "2026-11-19 23:00", freq="h", name="time")
    archive = pd.DataFrame({"speed": rng.uniform(300, 700, len(hours)), "bz_gsm": rng.normal(0, 3, len(hours)),
                            "by_gsm": rng.normal(0, 3, len(hours)), "density": 5.0, "b_scalar": 6.0}, index=hours)
    archive["omni_pressure"] = sw_archive.flow_pressure(archive["density"], archive["speed"])
    return daily, archive


def _fit(daily, archive):
    window = backtest.training_rows(daily, pd.Timestamp("2026-07-01"))
    return sw_shadow.SolarWindShadow().fit(window, sw_archive.daily_summary(archive), {t: SMALL for t in config.FORECAST_TARGETS})


def _live(origin):
    return pd.DataFrame({"model": "histgb", "lead": list(config.FORECAST_LEADS), "ap": 11.0, "kpmax": 3.0,
                         "origin": origin})


def test_features_match_validated_variant(setup):
    from src.forecast import validate_yearly as V
    daily, archive = setup
    sw = sw_archive.daily_summary(archive)
    V.SolarWind._cache = sw
    try:
        pd.testing.assert_frame_equal(V.SolarWindRec().features(daily, 2), sw_shadow.sw_features(daily, 2, sw))
    finally:
        V.SolarWind._cache = None


def test_status_and_fallback(setup):
    daily, archive = setup
    model = _fit(daily, archive)
    origin = pd.Timestamp("2026-11-18")
    full = sw_shadow.issue(daily, origin, _live(origin), archive, pd.Timestamp("2026-11-19 01:00"), model)
    assert (full["sw_status"] == "full").all() and (full["served"] == sw_shadow.NAME).all()
    assert (full["ap"] == full["ap_sw"]).all()
    short = sw_shadow.issue(daily, origin, _live(origin), archive.loc["2026-11-10":], pd.Timestamp("2026-11-19"), model)
    assert (short["sw_status"] == "no_echo").all() and (short["echo_days_missing"] == 9).all()
    none = sw_shadow.issue(daily, origin, _live(origin), archive.loc[:"2026-11-10"], pd.Timestamp("2026-11-19"), model)
    assert (none["sw_status"] == "no_sw").all() and (none["served"] == "histgb_fallback").all()
    assert (none["ap"] == 11.0).all() and (none["kpmax"] == 3.0).all()


def test_log_is_append_only():
    row = lambda o, ap: pd.DataFrame({"origin": [pd.Timestamp(o)], "lead": [1], "ap": [ap]})  # noqa: E731
    log = sw_shadow.append(pd.DataFrame(columns=sw_shadow.LOG_COLUMNS), row("2026-11-18", 5.0))
    log = sw_shadow.append(log, row("2026-11-18", 9.0))
    log = sw_shadow.append(log, row("2026-11-19", 7.0))
    assert log["ap"].tolist() == [5.0, 7.0]


def test_saved_bundle_loads():
    if not sw_shadow.BUNDLE.exists():
        pytest.skip("no bundle")
    m = sw_shadow.SolarWindShadow.load()
    assert m.version.startswith(sw_shadow.NAME) and len(m.columns_) == 45
