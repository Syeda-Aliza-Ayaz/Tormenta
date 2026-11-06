"""Merge OMNI (features) + GFZ (label) into the hourly modelling table.

Each hour h is labelled with the Kp of the 3-h block containing h. The table keeps
all hours (missing ones as NaN) and the GFZ definitive flag; the D=2 filter is applied
at training time so preliminary rows stay available for monitoring.
"""
import pandas as pd

from src import config
from src.ingest.fetch_gfz import kp_3hourly, load_gfz_daily
from src.ingest.fetch_omni import load_omni_lst


def build_hourly(omni: pd.DataFrame, gfz_daily: pd.DataFrame) -> pd.DataFrame:
    # End at the last hour with any solar-wind data: SPDF's current-year file can carry trailing fill
    # rows, and GFZ labels for those hours must not enter training with empty features
    omni = omni.loc[: omni[config.SW_FEATURES].dropna(how="all").index.max()]
    # Complete hourly grid so later .shift()/.rolling() never jump across gaps
    grid = pd.date_range(omni.index.min(), omni.index.max(), freq="h", name="time")
    df = omni.reindex(grid).drop(columns=["sunspot_r", "f107"])

    kp3 = kp_3hourly(gfz_daily)
    block = df.index.floor(f"{config.KP_BLOCK_HOURS}h")
    df[config.TARGET] = kp3["kp"].reindex(block).to_numpy()
    df["kp_definitive"] = kp3["definitive"].reindex(block).fillna(False).astype(bool).to_numpy()

    # Daily observed F10.7 on its own calendar day; features.py applies the 1-day causal shift
    df["f107_obs"] = gfz_daily["f107_obs"].reindex(df.index.normalize()).to_numpy()
    return df


def build_f107_history(gfz_daily: pd.DataFrame, path=config.F107_HISTORY) -> pd.Series:
    """Daily observed F10.7 file read by the live app for the trailing 81-day mean (last year kept)."""
    hist = gfz_daily["f107_obs"].dropna()
    hist = hist[hist.index > hist.index.max() - pd.Timedelta(days=365)]
    hist.to_csv(path, header=True)
    return hist


def save_processed(df: pd.DataFrame, path=config.PROCESSED_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)


def load_processed(path=config.PROCESSED_CSV) -> pd.DataFrame:
    return pd.read_csv(path, index_col="time", parse_dates=["time"])


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Missing-% per column, printed with row/column counts."""
    usable = df[config.TARGET].notna() & df["kp_definitive"]
    print(f"Rows (hours): {len(df):,}   Columns: {df.shape[1]}")
    print(f"Span: {df.index.min()} → {df.index.max()}")
    print(f"Rows with definitive Kp label: {usable.sum():,} "
          f"(~{usable.sum() // config.KP_BLOCK_HOURS:,} independent 3-h labels)")
    return (df.isna().mean() * 100).round(2).rename("missing_%").to_frame()


def check(df: pd.DataFrame) -> None:
    """Phase 1 sanity checks — raise if the table is malformed."""
    assert df.index.is_unique, "duplicate timestamps"
    assert (df.index.to_series().diff().dropna() == pd.Timedelta("1h")).all(), "hourly grid has holes"
    kp = df[config.TARGET].dropna()
    assert kp.between(0, 9).all(), "Kp outside [0, 9]"
    print("Sanity checks passed: unique timestamps, complete hourly grid, Kp in [0, 9].")


def main() -> pd.DataFrame:
    omni = load_omni_lst()
    gfz = load_gfz_daily()
    df = build_hourly(omni, gfz)
    check(df)
    save_processed(df)
    build_f107_history(gfz)
    print(summarize(df).to_string())
    return df


if __name__ == "__main__":
    main()
