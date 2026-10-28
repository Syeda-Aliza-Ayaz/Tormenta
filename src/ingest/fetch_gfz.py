"""GFZ Potsdam Kp index → 3-hourly target series (+ daily observed F10.7).

Source: GFZ German Research Centre for Geosciences, https://kp.gfz.de
Licence: CC BY 4.0 (Kp, F10.7). Sunspot numbers in the file are CC BY-NC and are not used.
"""
import pandas as pd
import requests

from src import config

KP_COLS = [f"kp{i}" for i in range(1, 9)]
GFZ_COLUMNS = (
    ["year", "month", "day", "days", "days_m", "bsr", "db"]
    + KP_COLS
    + [f"ap{i}" for i in range(1, 9)]
    + ["Ap", "SN", "f107_obs", "f107_adj", "D"]
)


def download_gfz(dest=config.GFZ_TXT) -> None:
    resp = requests.get(config.GFZ_URL, timeout=120)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)


def load_gfz_daily(path=config.GFZ_TXT) -> pd.DataFrame:
    """One row per UTC day: kp1–kp8, observed F10.7, definitive flag. Missing (-1) → NaN."""
    df = pd.read_csv(path, sep=r"\s+", comment="#", header=None, names=GFZ_COLUMNS)
    df.index = pd.to_datetime(df[["year", "month", "day"]])
    df.index.name = "date"

    df[KP_COLS] = df[KP_COLS].mask(df[KP_COLS] < 0)
    df["f107_obs"] = df["f107_obs"].mask(df["f107_obs"] <= 0)
    df["definitive"] = df["D"] == config.GFZ_DEFINITIVE
    return df[KP_COLS + ["f107_obs", "definitive"]]


def kp_3hourly(daily: pd.DataFrame) -> pd.DataFrame:
    """Melt kp1…kp8 into one series indexed by block start (00, 03, …, 21 UT)."""
    long = daily[KP_COLS + ["definitive"]].reset_index().melt(
        id_vars=["date", "definitive"], value_vars=KP_COLS, var_name="block", value_name="kp"
    )
    block = long["block"].str[2:].astype(int) - 1
    long["time"] = long["date"] + pd.to_timedelta(block * config.KP_BLOCK_HOURS, unit="h")
    return long.set_index("time").sort_index()[["kp", "definitive"]]
