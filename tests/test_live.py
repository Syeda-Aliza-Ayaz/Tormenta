"""Live path parity: SWPC-shaped 1-min data must give the same features as the training path."""
import numpy as np
import pandas as pd

from src import config
from src.features import build_features
from src.ingest import fetch_live
from tests.test_features import synthetic  # noqa: F401  (pytest fixture)


def _swpc_records(hourly: pd.DataFrame) -> list:
    """Expand hourly values into 60 identical SWPC-style minutes per hour (header row + rows)."""
    to_swpc = {v: k for k, v in fetch_live.SOLAR_WIND_COLUMNS.items()}
    minutes = hourly.reindex(pd.date_range(hourly.index[0], hourly.index[-1] + pd.Timedelta("59min"), freq="min"),
                             method="ffill").rename(columns=to_swpc)
    header = ["time_tag", *to_swpc.values(), "propagated_time_tag"]
    rows = [[(t - pd.Timedelta("1h")).strftime("%Y-%m-%dT%H:%M:%SZ"),
             *[None if pd.isna(v) else float(v) for v in row],
             t.strftime("%Y-%m-%dT%H:%M:%SZ")]
            for t, row in zip(minutes.index, minutes[list(to_swpc.values())].to_numpy())]
    return [header, *rows]


def test_live_and_training_paths_give_identical_features(synthetic):  # noqa: F811
    hourly, f107 = synthetic
    hourly = hourly.iloc[: 24 * 10].rename_axis("time")
    live_hourly = fetch_live.to_hourly(fetch_live.parse_solar_wind(_swpc_records(hourly)))
    pd.testing.assert_frame_equal(build_features(live_hourly, f107), build_features(hourly, f107), check_freq=False)


def test_hour_with_too_few_minutes_is_missing():
    idx = pd.date_range("2026-01-01 00:00", periods=60 + config.LIVE_MIN_MINUTES - 1, freq="min")
    minutes = pd.DataFrame({c: 1.0 for c in config.SW_FEATURES}, index=idx)
    hourly = fetch_live.to_hourly(minutes)
    assert hourly.iloc[0].notna().all()
    assert hourly.iloc[1].isna().all()


def test_f107_history_wins_over_feed():
    days = pd.date_range("2026-10-20", periods=5, freq="D")
    history = pd.Series([100.0, 101, 102, 103, 104], index=days)
    recent = pd.Series([0.0, 0, 200, 201], index=days[3:].append(pd.date_range("2026-10-25", periods=2)))
    merged = fetch_live.merge_f107(history, recent[~recent.index.duplicated()])
    assert merged.loc["2026-10-23"] == 103 and merged.loc["2026-10-25"] == 200
    assert merged.index.is_monotonic_increasing


def test_parse_kp_and_f107_formats():
    kp = fetch_live.parse_kp([{"time_tag": "2026-10-30T03:00:00", "Kp": 1.67, "a_running": 6, "station_count": 8}])
    assert kp.index[0] == pd.Timestamp("2026-10-30 03:00") and np.isclose(kp.iloc[0], 1.67)
    f = fetch_live.parse_f107([{"time_tag": "2026-10-29T20:00:00", "flux": 89}])
    assert f.index[0] == pd.Timestamp("2026-10-29") and f.iloc[0] == 89


def test_parse_gfz_nowcast():
    text = ("# header\n"
            "2026 10 30 06.0 07.50 34636.25000 34636.31250  1.000    4 0\n"
            "2026 10 30 09.0 10.50 34636.37500 34636.43750 -1.000   -1 0\n")
    kp = fetch_live.parse_gfz_nowcast(text)
    assert kp.index[0] == pd.Timestamp("2026-10-30 06:00") and kp.iloc[0] == 1.0
    assert np.isnan(kp.iloc[1])
