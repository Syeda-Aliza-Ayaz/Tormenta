"""NASA OMNI2 hourly solar-wind data → tidy hourly DataFrame.

Source: NASA GSFC SPDF OMNIWeb (https://omniweb.gsfc.nasa.gov), public domain.
Two inputs, one output schema (same columns, fills → NaN, naive-UTC hourly index):
  load_omni_lst   — the OMNIWeb subset (.lst) used to seed training in Phase 1
  load_omni_spdf  — SPDF yearly files omni2_YYYY.dat (all 55 OMNI2 words), used by the weekly retrain
"""
from pathlib import Path

import pandas as pd
import requests

from src import config

# 0-based word positions in omni2_YYYY.dat (OMNI2 hourly format, 55 words per line)
SPDF_WORDS = {
    "year": 0, "doy": 1, "hour": 2,
    "b_scalar": 8, "bx": 12, "by_gsm": 15, "bz_gsm": 16,
    "temperature": 22, "density": 23, "speed": 24,
    "omni_pressure": 28, "omni_efield": 35, "omni_beta": 36, "omni_mach_a": 37, "omni_mach_ms": 54,
    "sunspot_r": 39, "f107": 50,
}
SPDF_DIR = config.RAW_DIR / "spdf"


def load_omni_lst(path=config.OMNI_LST) -> pd.DataFrame:
    """Parse the OMNIWeb .lst subset: fill sentinels → NaN, UTC time index."""
    return _clean(pd.read_csv(path, sep=r"\s+", header=None, names=config.OMNI_LST_COLUMNS))


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    """Fill sentinels → NaN and a time index; shared by both parsers so the schema is identical."""
    # Sentinels are column-specific (999.9, 9999., 9999999., …); legit values never reach them
    for col, fill in config.OMNI_FILL.items():
        df[col] = df[col].mask(df[col] >= fill - 1e-6)
    df["time"] = (
        pd.to_datetime(df["year"].astype(int).astype(str), format="%Y")
        + pd.to_timedelta(df["doy"] - 1, unit="D")
        + pd.to_timedelta(df["hour"], unit="h")
    )
    return df.drop(columns=["year", "doy", "hour"]).set_index("time").sort_index()


def parse_spdf(path) -> pd.DataFrame:
    """One omni2_YYYY.dat file → the same columns (in the same order) as load_omni_lst."""
    words = pd.read_csv(path, sep=r"\s+", header=None)
    if words.shape[1] != 55:
        raise ValueError(f"{path}: expected 55 OMNI2 words per line, got {words.shape[1]}")
    df = pd.DataFrame({col: words[i] for col, i in SPDF_WORDS.items()})[config.OMNI_LST_COLUMNS]
    return _clean(df.astype(float))


def download_spdf_year(year: int, dest_dir: Path = SPDF_DIR) -> Path:
    resp = requests.get(config.OMNI_SPDF_URL.format(year=year), timeout=300)
    resp.raise_for_status()
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"omni2_{year}.dat"
    path.write_bytes(resp.content)
    return path


def load_omni_spdf(first_year: int, last_year: int, download: bool = True) -> pd.DataFrame:
    """All yearly files from first_year to last_year (the current year's file may not exist yet)."""
    frames = []
    for year in range(first_year, last_year + 1):
        path = SPDF_DIR / f"omni2_{year}.dat"
        try:
            if download:
                path = download_spdf_year(year)
        except requests.HTTPError as exc:
            if year == last_year and exc.response is not None and exc.response.status_code == 404:
                continue                          # current year not published yet
            raise
        frames.append(parse_spdf(path))
    return pd.concat(frames).sort_index()
