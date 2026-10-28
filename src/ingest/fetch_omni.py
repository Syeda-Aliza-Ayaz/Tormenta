"""NASA OMNI2 hourly solar-wind data → tidy hourly DataFrame.

Source: NASA GSFC SPDF OMNIWeb (https://omniweb.gsfc.nasa.gov), public domain.
Phase 1 reads the OMNIWeb subset (.lst); the SPDF yearly-file parser is added in Phase 6.
Times are naive UTC throughout the project.
"""
import pandas as pd

from src import config


def load_omni_lst(path=config.OMNI_LST) -> pd.DataFrame:
    """Parse the OMNIWeb .lst subset: fill sentinels → NaN, UTC time index."""
    df = pd.read_csv(path, sep=r"\s+", header=None, names=config.OMNI_LST_COLUMNS)

    # Sentinels are column-specific (999.9, 9999., 9999999., …); legit values never reach them
    for col, fill in config.OMNI_FILL.items():
        df[col] = df[col].mask(df[col] >= fill - 1e-6)

    df["time"] = (
        pd.to_datetime(df["year"].astype(str), format="%Y")
        + pd.to_timedelta(df["doy"] - 1, unit="D")
        + pd.to_timedelta(df["hour"], unit="h")
    )
    return df.drop(columns=["year", "doy", "hour"]).set_index("time").sort_index()
