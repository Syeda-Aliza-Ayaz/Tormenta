"""Solar-wind archive for the forecaster.

The SWPC propagated solar-wind feed holds only the last 7 days, while the solar-wind forecast features need up to
27 days of history (the 27-day echo, D-68). The daily job therefore keeps its own hourly archive of the feed:

  forecasts/solar_wind_hourly.csv   one row per UTC hour (propagated, arrival-at-Earth time): speed, Bz, By,
                                    density, |B|, flow pressure, and the time it was first archived.

The archive holds real-time data only; it is never overwritten with OMNI. Once OMNI covers the same hours, the two
can be compared hour by hour, which is the real-time vs archive check that D-69 needs.

Rules:
  - An archived hour is replaced only when a later fetch has more non-missing values for it, so a later fetch can
    fill gaps but never erase data.
  - Hours at or after the current UTC hour are never stored; they are incomplete.

`daily_summary` turns hourly rows into the daily features used by the yearly validation (D-68), so training and live
forecasts share one definition.
"""
import argparse

import pandas as pd

from src import config

COLUMNS = ["speed", "bz_gsm", "by_gsm", "density", "b_scalar", "omni_pressure"]
MIN_HOURS_PER_DAY = 12
ECHO_DAYS_BACK = range(19, 28)     # days before the issue day read by the 27-day echo for lead days 1-7 (±1 day)


def flow_pressure(density, speed):
    """Flow pressure in nPa with OMNI's definition (2e-6 · n · V², which includes the usual alpha-particle share)."""
    return 2e-6 * density * speed ** 2


def from_live(hourly: pd.DataFrame, fetched_at: pd.Timestamp) -> pd.DataFrame:
    """Hourly SWPC frame (fetch_live.fetch_solar_wind) → archive columns."""
    out = hourly.reindex(columns=["speed", "bz_gsm", "by_gsm", "density", "b_scalar"]).astype(float)
    out["omni_pressure"] = flow_pressure(out["density"], out["speed"])
    out["fetched_at"] = fetched_at.floor("s")
    out.index.name = "time"
    return out


def load(path=None) -> pd.DataFrame:
    path = path or config.SOLAR_WIND_ARCHIVE
    if not path.exists():
        return pd.DataFrame(columns=[*COLUMNS, "fetched_at"], index=pd.DatetimeIndex([], name="time"))
    return pd.read_csv(path, parse_dates=["time", "fetched_at"], index_col="time")


def merge(archive: pd.DataFrame, new: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Add new hourly rows to the archive under the rules in the module docstring."""
    new = new[new.index < now.floor("h")]
    new = new[new[COLUMNS].notna().any(axis=1)]
    if new.empty:
        return archive
    old_count = archive.reindex(new.index)[COLUMNS].notna().sum(axis=1)
    take = new[new[COLUMNS].notna().sum(axis=1) > old_count]
    out = pd.concat([archive.drop(index=take.index, errors="ignore"), take]) if len(archive) else take
    out.index.name = "time"
    return out.sort_index()


def update(fetch=None, now: pd.Timestamp = None, path=None) -> pd.DataFrame:
    """Fetch the live feed and merge it into the archive file. Returns the archive (unchanged if the fetch fails)."""
    from src.ingest import fetch_live
    now = now or pd.Timestamp.now(tz="UTC").tz_localize(None)
    path = path or config.SOLAR_WIND_ARCHIVE
    archive = load(path)
    try:
        live = from_live((fetch or fetch_live.fetch_solar_wind)(), now)
    except Exception as exc:                      # noqa: BLE001 - the archive must never block the forecast
        print(f"WARNING: solar wind not archived ({type(exc).__name__}: {exc})")
        return archive
    out = merge(archive, live, now)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, float_format="%.5g", date_format="%Y-%m-%d %H:%M:%S")
    print(f"solar-wind archive: {len(out)} hours ({len(out) - len(archive):+d} this run), last {out.index.max()}")
    return out


def omni_hourly() -> pd.DataFrame:
    """Hourly OMNI solar wind for the forecaster: the processed table, extended with NASA's yearly SPDF files
    (data/raw/spdf/omni2_YYYY.dat) for hours after the table's last row. Never overwrites a row of the table."""
    import glob
    from src.ingest import fetch_omni
    h = pd.read_csv(config.PROCESSED_CSV, usecols=["time", *COLUMNS], parse_dates=["time"]).set_index("time")
    last = h.dropna(subset=["speed"]).index.max()
    years = sorted(int(p[-8:-4]) for p in glob.glob(str(fetch_omni.SPDF_DIR / "omni2_*.dat")) if int(p[-8:-4]) >= last.year)
    if years:
        extra = fetch_omni.load_omni_spdf(years[0], years[-1], download=False)
        extra = extra.loc[extra.index > last, COLUMNS].dropna(how="all")
        h = pd.concat([h.loc[:last], extra])
    return h.sort_index()


def daily_summary(hourly: pd.DataFrame) -> pd.DataFrame:
    """Daily solar-wind features (UTC days). A day needs at least 12 hourly speed values, otherwise it is blank."""
    h = hourly[COLUMNS].astype(float)
    bs = (-h["bz_gsm"]).clip(lower=0)                               # southward field, the part that drives storms
    h = h.assign(vbs=h["speed"] * bs / 1000)                        # rectified electric field (mV/m)
    g = h.resample("D")
    d = pd.DataFrame({"sw_speed": g["speed"].mean(), "sw_speed_max": g["speed"].max(), "sw_bz": g["bz_gsm"].mean(),
                      "sw_bz_min": g["bz_gsm"].min(), "sw_vbs": g["vbs"].mean(), "sw_density": g["density"].mean(),
                      "sw_b": g["b_scalar"].mean(), "sw_pressure_max": g["omni_pressure"].max(),
                      "sw_by": g["by_gsm"].mean()})
    return d.where(g["speed"].count() >= MIN_HOURS_PER_DAY)


def readiness(archive: pd.DataFrame, origin: pd.Timestamp) -> dict:
    """Which solar-wind inputs a forecast issued from `origin` (the last complete day) can use."""
    hours = archive["speed"].notna().groupby(archive.index.floor("D")).sum() if len(archive) else pd.Series(dtype=int)
    usable = lambda back: hours.get(origin - pd.Timedelta(days=back), 0) >= MIN_HOURS_PER_DAY  # noqa: E731
    return {"today": bool(usable(0)), "yesterday": bool(usable(1)),
            "echo": all(usable(b) for b in ECHO_DAYS_BACK),
            "echo_days_missing": sum(not usable(b) for b in ECHO_DAYS_BACK)}


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--update", action="store_true", help="fetch the live feed and archive it")
    p.add_argument("--status", action="store_true", help="what a forecast issued today could use")
    a = p.parse_args()
    if a.update:
        update()
    if a.status:
        origin = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() - pd.Timedelta(days=1)
        print(f"origin {origin.date()}: {readiness(load(), origin)}")


if __name__ == "__main__":
    main()
