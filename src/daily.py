"""GFZ → the daily table the forecaster trains, forecasts and verifies on (PLAN.md §3).

One row per UTC day, 1932 → the last day GFZ has published (usually yesterday):
  ap        daily Ap (GFZ)                       target + input
  kpmax     largest of the eight 3-hourly Kp     target + input
  f107_obs  observed (Penticton) F10.7           input (starts 1947-02-14)
  gfz_flag  0 nowcast · 1 provisional · 2 definitive
  definitive  gfz_flag == 2: training and final scores use these days only

    python -m src.daily            # download GFZ, rebuild data/processed/daily.csv, print a summary
    python -m src.daily --no-download
"""
import argparse

import pandas as pd

from src import config
from src.ingest.fetch_gfz import KP_COLS, download_gfz, load_gfz_daily


def build_daily(gfz_daily: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame({
        "ap": gfz_daily["ap_daily"],
        # max over the day's blocks; a day with any missing block has no reliable maximum
        "kpmax": gfz_daily[KP_COLS].max(axis=1).where(gfz_daily[KP_COLS].notna().all(axis=1)),
        "f107_obs": gfz_daily["f107_obs"],
        "gfz_flag": gfz_daily["gfz_flag"].astype(int),
        "definitive": gfz_daily["definitive"].astype(bool),
    })
    # Complete daily grid so .shift(27) always means "27 days earlier"
    grid = pd.date_range(df.index.min(), df.index.max(), freq="D", name="date")
    out = df.reindex(grid)
    out["definitive"] = out["definitive"].fillna(False).astype(bool)
    return out


def check(df: pd.DataFrame) -> None:
    """Raise if the daily table is malformed."""
    assert df.index.is_unique, "duplicate days"
    assert (df.index.to_series().diff().dropna() == pd.Timedelta("1D")).all(), "daily grid has holes"
    assert df["ap"].dropna().between(0, 400).all(), "Ap outside [0, 400]"
    assert df["kpmax"].dropna().between(0, 9).all(), "max Kp outside [0, 9]"
    # definitive days form one block at the start: GFZ never finalises a day after a later one
    # (days absent from the file are gaps, not "not yet definitive", so they are skipped)
    flag = df.loc[df["gfz_flag"].notna(), "definitive"].to_numpy()
    if not flag.all():
        first_open = flag.argmin()
        assert not flag[first_open:].any(), "definitive day after a non-definitive one"


def save_daily(df: pd.DataFrame, path=config.DAILY_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)


def load_daily(path=config.DAILY_CSV) -> pd.DataFrame:
    return pd.read_csv(path, index_col="date", parse_dates=["date"])


def last_definitive(df: pd.DataFrame) -> pd.Timestamp:
    return df.index[df["definitive"]].max()


def main(download: bool = True) -> pd.DataFrame:
    if download:
        download_gfz()
    df = build_daily(load_gfz_daily())
    check(df)
    save_daily(df)
    flags = df["gfz_flag"].value_counts().sort_index().to_dict()
    print(f"daily table {df.index.min().date()} -> {df.index.max().date()} ({len(df):,} days) | "
          f"definitive to {last_definitive(df).date()} | flags {flags} | "
          f"F10.7 from {df['f107_obs'].first_valid_index().date()}")
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true", help="use the GFZ file already in data/raw/")
    main(download=not ap.parse_args().no_download)
