"""Live NOAA SWPC data → the same hourly raw columns and daily F10.7 that training uses.

Sources (no auth, checked 2026-10-30):
  solar wind — products/geospace/propagated-solar-wind.json: 7 days of 1-min data from the active
               L1 spacecraft, IMF in GSM, already propagated to Earth (like OMNI's time shift)
  F10.7      — data/f107_history.csv (GFZ observed flux) + products/10cm-flux-30-day.json
  Kp         — products/noaa-planetary-k-index.json (NOAA estimated Kp) and GFZ's quick-look
               Kp_ap_nowcast.txt (same producer as the training labels); comparison only

Hourly averaging mirrors OMNI: the hour labelled HH is the mean of minutes HH:00–HH:59, and
|B| (b_scalar) is the mean of the 1-min field magnitudes.
"""
import pandas as pd
import requests

from src import config

# SWPC field → training column
SOLAR_WIND_COLUMNS = {"bt": "b_scalar", "bx": "bx", "by": "by_gsm", "bz": "bz_gsm",
                      "temperature": "temperature", "density": "density", "speed": "speed"}


def fetch_json(url: str):
    resp = requests.get(url, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _naive_utc(times) -> pd.DatetimeIndex:
    t = pd.to_datetime(times, utc=True)
    return pd.DatetimeIndex(t).tz_localize(None)


def parse_solar_wind(records) -> pd.DataFrame:
    """1-min frame indexed by propagated (arrival-at-Earth) time, training column names."""
    header, rows = records[0], records[1:]
    df = pd.DataFrame(rows, columns=header)
    out = df[list(SOLAR_WIND_COLUMNS)].apply(pd.to_numeric, errors="coerce").rename(columns=SOLAR_WIND_COLUMNS)
    out.index = _naive_utc(df["propagated_time_tag"]).rename("time")   # same index name as training data
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out[config.SW_FEATURES]


def to_hourly(minutes: pd.DataFrame) -> pd.DataFrame:
    """Hourly means on a complete grid; hours with too few samples in a column become NaN."""
    grouped = minutes.resample("h")
    hourly = grouped.mean().where(grouped.count() >= config.LIVE_MIN_MINUTES)
    return hourly.asfreq("h")


def parse_f107(records) -> pd.Series:
    """Daily observed F10.7 (measured ~20 UT) indexed by date."""
    df = pd.DataFrame(records)
    s = pd.Series(pd.to_numeric(df["flux"], errors="coerce").to_numpy(),
                  index=_naive_utc(df["time_tag"]).normalize(), name="f107_obs")
    return s[~s.index.duplicated(keep="last")].sort_index()


def merge_f107(history: pd.Series, recent: pd.Series) -> pd.Series:
    """History file (GFZ) first; SWPC fills only the days the history does not have yet."""
    return pd.concat([history, recent[~recent.index.isin(history.index)]]).sort_index()


def load_f107_history(path=config.F107_HISTORY) -> pd.Series:
    return pd.read_csv(path, index_col="date", parse_dates=["date"])["f107_obs"]


def parse_kp(records) -> pd.Series:
    """NOAA estimated Kp, indexed by 3-h block start."""
    df = pd.DataFrame(records)
    return pd.Series(pd.to_numeric(df["Kp"], errors="coerce").to_numpy(),
                     index=_naive_utc(df["time_tag"]), name="kp_swpc").sort_index()


def parse_gfz_nowcast(text: str) -> pd.Series:
    """GFZ quick-look Kp (one row per 3-h block; -1 = not yet available), indexed by block start."""
    rows = [line.split() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    df = pd.DataFrame([r[:8] for r in rows], columns=["year", "month", "day", "hour", "hour_m", "days", "days_m", "kp"])
    index = pd.to_datetime(df[["year", "month", "day"]].astype(int)) + pd.to_timedelta(df["hour"].astype(float), unit="h")
    kp = pd.Series(df["kp"].astype(float).to_numpy(), index=pd.DatetimeIndex(index), name="kp_gfz")
    return kp.where(kp >= 0)


def fetch_solar_wind() -> pd.DataFrame:
    return to_hourly(parse_solar_wind(fetch_json(config.SWPC_SOLAR_WIND)))


def fetch_f107() -> pd.Series:
    return merge_f107(load_f107_history(), parse_f107(fetch_json(config.SWPC_F107)))


def fetch_swpc_kp() -> pd.Series:
    return parse_kp(fetch_json(config.SWPC_KP))


def fetch_gfz_nowcast() -> pd.Series:
    resp = requests.get(config.GFZ_NOWCAST_URL, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return parse_gfz_nowcast(resp.text)
