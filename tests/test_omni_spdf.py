"""SPDF yearly-file parser must give exactly what the OMNIWeb .lst parser gave for training.

Reference: tests/data/omni_lst_2024-03-01_03.csv, three days cut from the Phase 1 .lst seed.
The online test downloads omni2_2024.dat (runs in GitHub Actions; skipped when SPDF is unreachable).
"""
import numpy as np
import pandas as pd
import pytest
import requests

from src import config
from src.ingest import fetch_omni
from src.preprocessing import build_hourly

REFERENCE = config.ROOT / "tests" / "data" / "omni_lst_2024-03-01_03.csv"


def _reference() -> pd.DataFrame:
    return pd.read_csv(REFERENCE, index_col="time", parse_dates=["time"])


def _as_spdf_lines(ref: pd.DataFrame) -> str:
    """Write reference rows back out as 55-word OMNI2 lines (fills restored, unused words = 0)."""
    lines = []
    for t, row in ref.iterrows():
        words = ["0"] * 55
        words[0], words[1], words[2] = str(t.year), str(t.day_of_year), str(t.hour)
        for col, i in fetch_omni.SPDF_WORDS.items():
            if col in row.index:
                words[i] = repr(config.OMNI_FILL[col] if pd.isna(row[col]) else float(row[col]))
        lines.append(" ".join(words))
    return "\n".join(lines) + "\n"


def test_spdf_parser_matches_lst_schema_offline(tmp_path):
    ref = _reference()
    ref.iloc[5, ref.columns.get_loc("bz_gsm")] = np.nan          # a fill value must come back as NaN
    path = tmp_path / "omni2_2024.dat"
    path.write_text(_as_spdf_lines(ref))
    parsed = fetch_omni.parse_spdf(path)
    pd.testing.assert_frame_equal(parsed, ref, check_dtype=False, check_names=False, check_freq=False)


def test_spdf_parser_against_real_2024_file(tmp_path):
    try:
        path = fetch_omni.download_spdf_year(2024, tmp_path)
    except requests.RequestException:
        pytest.skip("SPDF not reachable from this network")
    parsed = fetch_omni.parse_spdf(path)
    ref = _reference()
    cols = [c for c in ref.columns if c != "sunspot_r"]               # sunspot numbers get revised
    pd.testing.assert_frame_equal(parsed.loc[ref.index, cols], ref[cols], check_dtype=False,
                                  check_names=False, check_freq=False, atol=1e-6)


def test_trailing_fill_hours_are_dropped():
    ref = _reference()
    tail = pd.DataFrame(np.nan, index=pd.date_range(ref.index[-1] + pd.Timedelta("1h"), periods=10, freq="h"),
                        columns=ref.columns)
    days = pd.date_range("2024-02-01", "2024-03-31", freq="D", name="date")
    gfz = pd.DataFrame({**{f"kp{i}": 2.0 for i in range(1, 9)}, "f107_obs": 150.0, "definitive": True}, index=days)
    hourly = build_hourly(pd.concat([ref, tail]), gfz)
    assert hourly.index.max() == ref.index.max()
