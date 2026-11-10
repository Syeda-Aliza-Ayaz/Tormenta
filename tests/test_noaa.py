"""NOAA benchmark parsers against real saved products (tests/data/noaa_*.txt)."""
from pathlib import Path

import pandas as pd

from src.ingest import fetch_noaa

DATA = Path(__file__).parent / "data"


def _read(name):
    return (DATA / name).read_text()


def test_rsga_crosses_year_and_aligns_origin():
    df = fetch_noaa.parse_rsga(_read("noaa_rsga_20251231.txt"))
    assert df["issued"].iloc[0] == pd.Timestamp("2025-12-31 22:00")
    assert (df["origin"] == pd.Timestamp("2025-12-31")).all()          # issued 22:00 on D → origin D
    assert df["target_date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert df["lead"].tolist() == [1, 2, 3]
    assert df["ap"].tolist() == [18.0, 16.0, 42.0]


def test_rsga_leap_day():
    """Regression: '29 Feb' made the year-guess fail on non-leap neighbour years (2020-02-28 report)."""
    text = ":Issued: 2020 Feb 28 2200 UTC\nPredicted Afr/Ap 29 Feb-02 Mar  005/005-005/005-007/008\n"
    df = fetch_noaa.parse_rsga(text)
    assert df["target_date"].dt.strftime("%Y-%m-%d").tolist() == ["2020-02-29", "2020-03-01", "2020-03-02"]


def test_rsga_missing_forecast_value_is_nan():
    text = ":Issued: 2025 Jan 01 2200 UTC\nPredicted Afr/Ap 02 Jan-04 Jan  012/015-///-005/005\n"
    assert fetch_noaa.parse_rsga(text)["ap"].isna().tolist() == [False, True, False]


def test_27day_outlook():
    df = fetch_noaa.parse_27do(_read("noaa_27do_20261109.txt"))
    assert len(df) == 27
    assert df["origin"].iloc[0] == pd.Timestamp("2026-11-08")          # issued 02:58 on D → origin D−1
    assert df["lead"].tolist() == list(range(1, 28))
    assert df.iloc[0][["f107", "ap", "kpmax"]].tolist() == [125.0, 15.0, 4.0]


def test_3day_forecast_daily_max():
    df = fetch_noaa.parse_3day(_read("noaa_3day_20261110.txt"))
    assert df["target_date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-11-10", "2026-11-11", "2026-11-12"]
    assert df["lead"].tolist() == [1, 2, 3]
    assert df["kpmax"].tolist() == [3.67, 3.0, 3.0]


def test_3day_ignores_noaa_scale_annotations():
    text = (":Issued: 2026 Nov 10 0030 UTC\nNOAA Kp index breakdown Dec 31-Jan 02 2027\n\n"
            "             Dec 31       Jan 01       Jan 02\n"
            + "".join(f"{h:02d}-{h + 3:02d}UT       5.67 (G2)    3.00         1.00\n" for h in range(0, 24, 3)))
    df = fetch_noaa.parse_3day(text)
    assert df["kpmax"].tolist() == [5.67, 3.0, 1.0]
