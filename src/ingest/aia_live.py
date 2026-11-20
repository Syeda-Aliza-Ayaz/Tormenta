"""Daily coronal-hole features from the near-real-time AIA 193 Å image (DECISIONS D-70, D-76).

The JSOC archive lags about 10 days; its near-real-time folder has the same 1024×1024 image at 00:00 UTC the same
day (D-70 live check: features agree with the archive, correlation 1.000). The daily job calls `update()`, which
fetches the 00:00 UTC image for each of the last few days, computes the features with the shared code
(`src/forecast/imagery.py`), and appends them to

  forecasts/imagery_daily.csv   date, ch_band_low, ch_band, ch_east, ch_disk, ch_dark, source, logged_at

Append-only: a day already logged keeps its values. Image files are kept only while their features are computed.
A failure only warns; it never blocks the forecast.
"""
import tempfile
from pathlib import Path

import pandas as pd
import requests

from src import config
from src.forecast import imagery

NRT_URL = "https://jsoc1.stanford.edu/data/aia/synoptic/nrt/{d:%Y/%m/%d}/H0000/AIA{d:%Y%m%d}_000000_0193.fits"
DAYS_BACK = 3


def load(path=None) -> pd.DataFrame:
    path = path or config.IMAGERY_LOG
    if not path.exists():
        return pd.DataFrame(columns=[*imagery.COLUMNS, "source", "logged_at"], index=pd.DatetimeIndex([], name="date"))
    return pd.read_csv(path, parse_dates=["date", "logged_at"], index_col="date")


def fetch_day(day: pd.Timestamp, folder: Path, get=requests.get):
    """Features of `day`'s 00:00 UTC near-real-time image, or None if missing or unusable."""
    r = get(NRT_URL.format(d=day), timeout=120)
    if r.status_code != 200 or not r.content.startswith(b"SIMPLE"):
        return None
    path = folder / f"AIA{day:%Y%m%d}_0000_0193.fits"
    path.write_bytes(r.content)
    return imagery.features_from_file(str(path))[1]


def update(now: pd.Timestamp = None, path=None, fetch=None) -> pd.DataFrame:
    now = now or pd.Timestamp.now(tz="UTC").tz_localize(None)
    path = path or config.IMAGERY_LOG
    log = load(path)
    today = now.normalize()
    days = [today - pd.Timedelta(days=k) for k in range(DAYS_BACK, -1, -1)]
    new = {}
    with tempfile.TemporaryDirectory() as tmp:
        for day in days:
            if day in log.index:
                continue
            try:
                feats = (fetch or fetch_day)(day, Path(tmp))
            except Exception as exc:                  # noqa: BLE001 - the log must never block the forecast
                print(f"WARNING: image for {day.date()} not processed ({type(exc).__name__}: {exc})")
                continue
            if feats:
                new[day] = {**feats, "source": "jsoc_nrt", "logged_at": now.floor("s")}
    if new:
        add = pd.DataFrame.from_dict(new, orient="index")
        add.index.name = "date"
        log = pd.concat([log, add]).sort_index() if len(log) else add
        path.parent.mkdir(parents=True, exist_ok=True)
        log.to_csv(path, float_format="%.4f", date_format="%Y-%m-%d")
    print(f"imagery log: {len(log)} days ({len(new):+d} this run), last {log.index.max() if len(log) else '-'}")
    return log


if __name__ == "__main__":
    update()
