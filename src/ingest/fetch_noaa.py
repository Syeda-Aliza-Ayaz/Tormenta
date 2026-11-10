"""NOAA SWPC forecasts → tables we can score like our own (benchmark only, never model inputs; DECISIONS D-06).

  RSGA (archived daily, ftp warehouse)  line "Predicted Afr/Ap 02 Jan-04 Jan  012/015-012/015-005/005" → Ap D+1..D+3
  27-day outlook (live text, weekly)    daily F10.7, Ap and largest Kp for 27 days — NOT archived, so saved daily
  3-day forecast (live text, daily)     3-hourly Kp for 3 days → daily max Kp

Every parser returns rows with `issued` (UTC timestamp), `origin`, `lead`, `target_date`. The origin is the last day
whose data NOAA had (almost) complete: the UTC date of (issued − 3 h). So a report issued 22:00 on D has origin D,
and the outlook issued 02:58 on D has origin D−1, which matches our own forecasts, issued about 02:00 on D+1 with
origin D.

    python -m src.ingest.fetch_noaa --rsga 2017 2026    # backfill data/noaa_rsga_ap.csv (one-off; ~10 min)
"""
import argparse
import ftplib
import io
import re
import tarfile

import numpy as np
import pandas as pd
import requests

from src import config

FTP_HOST = "ftp.swpc.noaa.gov"
ISSUED = re.compile(r"^:Issued:\s+(\d{4} \w{3} \d{1,2} \d{4}) UTC", re.M)
ORIGIN_OFFSET = pd.Timedelta(hours=3)


def _issued(text: str) -> pd.Timestamp:
    m = ISSUED.search(text)
    if not m:
        raise ValueError("no ':Issued:' line")
    return pd.to_datetime(m.group(1), format="%Y %b %d %H%M")


def _origin(issued: pd.Timestamp) -> pd.Timestamp:
    return (issued - ORIGIN_OFFSET).normalize()


def _date_near(day_month: str, issued: pd.Timestamp) -> pd.Timestamp:
    """'02 Jan' or 'Jan 02' without a year → the date closest to the issue date (handles Dec → Jan, and
    29 Feb, which exists only in leap years)."""
    candidates = []
    for k in (-1, 0, 1):
        for fmt in ("%d %b %Y", "%b %d %Y"):
            try:
                candidates.append(pd.to_datetime(f"{day_month} {issued.year + k}", format=fmt))
            except ValueError:
                pass
    if not candidates:
        raise ValueError(f"unreadable date {day_month!r}")
    return min(candidates, key=lambda d: abs(d - issued))


def _rows(issued, dates, **values) -> pd.DataFrame:
    origin = _origin(issued)
    dates = pd.DatetimeIndex(dates)
    return pd.DataFrame({"issued": issued, "origin": origin, "lead": (dates - origin).days,
                         "target_date": dates, **values})


# ── RSGA: NOAA predicted Ap for days 1–3 ─────────────────────────────────────
RSGA_AP = re.compile(r"Predicted Afr/Ap\s+(\d{1,2} \w{3})-(\d{1,2} \w{3})\s+(\S+)")


def parse_rsga(text: str) -> pd.DataFrame:
    issued = _issued(text)
    m = RSGA_AP.search(text)
    if not m:
        return _rows(issued, [], ap=[])
    first = _date_near(m.group(1), issued)
    triples = m.group(3).split("-")
    ap = [float(t.split("/")[1]) if re.fullmatch(r"\d+/\d+", t) else np.nan for t in triples]
    return _rows(issued, pd.date_range(first, periods=len(ap), freq="D"), ap=ap)


def _parse_many(texts) -> pd.DataFrame:
    frames = []
    for name, text in texts:
        try:
            frames.append(parse_rsga(text))
        except ValueError as exc:
            print(f"skipped {name}: {exc}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_rsga_year(year: int, ftp: ftplib.FTP) -> pd.DataFrame:
    """A finished year is one tarball; the current year is a folder of daily files."""
    folder = f"/pub/warehouse/{year}"
    names = ftp.nlst(folder)
    tarball = f"{year}_RSGA.tar.gz"
    if any(n.endswith(tarball) for n in names):
        buf = io.BytesIO()
        ftp.retrbinary(f"RETR {folder}/{tarball}", buf.write)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:   # read members in memory, never extracted to disk
            texts = [(m.name, tar.extractfile(m).read().decode("ascii", "replace"))
                     for m in tar.getmembers() if m.isfile() and m.name.endswith("RSGA.txt")]
    else:
        texts = []
        for name in sorted(n for n in ftp.nlst(f"{folder}/RSGA") if n.endswith("RSGA.txt")):
            buf = io.BytesIO()
            ftp.retrbinary(f"RETR {name}", buf.write)
            texts.append((name, buf.getvalue().decode("ascii", "replace")))
    return _parse_many(texts)


RSGA_CACHE = config.RAW_DIR / "noaa_rsga"     # one parsed CSV per year (not committed)
FTP_RETRIES = 3


def _fetch_year_with_retries(year: int) -> pd.DataFrame:
    """A fresh connection per attempt: one slow transfer must not lose the whole backfill."""
    for attempt in range(1, FTP_RETRIES + 1):
        try:
            ftp = ftplib.FTP(FTP_HOST, timeout=3 * config.REQUEST_TIMEOUT)
            ftp.login()
            try:
                return fetch_rsga_year(year, ftp)
            finally:
                try:
                    ftp.quit()
                except (OSError, ftplib.Error):
                    pass
        except (OSError, ftplib.Error) as exc:
            print(f"RSGA {year}: attempt {attempt} failed ({type(exc).__name__}: {exc})")
    raise RuntimeError(f"RSGA {year}: all {FTP_RETRIES} attempts failed")


def build_rsga_archive(first_year: int, last_year: int, path=config.NOAA_RSGA_CSV) -> pd.DataFrame:
    """Finished years are cached after their first download; the current year is always refetched."""
    RSGA_CACHE.mkdir(parents=True, exist_ok=True)
    this_year = pd.Timestamp.now(tz="UTC").year
    frames = []
    for year in range(first_year, last_year + 1):
        cache = RSGA_CACHE / f"{year}.csv"
        if cache.exists() and year < this_year:
            df = pd.read_csv(cache, parse_dates=["issued", "origin", "target_date"])
            source = "cached"
        else:
            df = _fetch_year_with_retries(year)
            df.to_csv(cache, index=False)
            source = "downloaded"
        print(f"RSGA {year}: {df['issued'].nunique() if len(df) else 0} reports ({source})")
        frames.append(df)
    out = (pd.concat(frames, ignore_index=True)
           .drop_duplicates(subset=["issued", "target_date"], keep="last")
           .sort_values(["issued", "lead"], ignore_index=True))
    out.to_csv(path, index=False)
    return out


def load_rsga(path=config.NOAA_RSGA_CSV) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["issued", "origin", "target_date"])


# ── Live products ────────────────────────────────────────────────────────────
OUTLOOK_ROW = re.compile(r"^(\d{4} \w{3} \d{2})\s+(\d+)\s+(\d+)\s+(\d+)\s*$", re.M)


def parse_27do(text: str) -> pd.DataFrame:
    issued = _issued(text)
    rows = OUTLOOK_ROW.findall(text)
    dates = [pd.to_datetime(r[0], format="%Y %b %d") for r in rows]
    return _rows(issued, dates, f107=[float(r[1]) for r in rows], ap=[float(r[2]) for r in rows],
                 kpmax=[float(r[3]) for r in rows])


KP_HEADER = re.compile(r"NOAA Kp index breakdown (\w{3} \d{1,2})-(\w{3} \d{1,2}) (\d{4})")
KP_ROW = re.compile(r"^\d{2}-\d{2}UT\s+(.*)$", re.M)


def parse_3day(text: str) -> pd.DataFrame:
    """Daily max of NOAA's 3-hourly Kp forecast (NOAA-scale annotations like '(G1)' are ignored)."""
    issued = _issued(text)
    m = KP_HEADER.search(text)
    if not m:
        return _rows(issued, [], kpmax=[])
    first = _date_near(m.group(1), issued)
    block = text[m.end():]
    values = [[float(v) for v in re.findall(r"\d+\.\d+", row)] for row in KP_ROW.findall(block)[:8]]
    kp = np.array(values)                                   # 8 blocks × 3 days
    return _rows(issued, pd.date_range(first, periods=kp.shape[1], freq="D"), kpmax=kp.max(axis=0))


def fetch_text(url: str) -> str:
    resp = requests.get(url, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rsga", nargs=2, type=int, metavar=("FIRST_YEAR", "LAST_YEAR"), required=True)
    a = ap.parse_args()
    df = build_rsga_archive(*a.rsga)
    print(f"saved {len(df):,} rows, {df['issued'].nunique():,} reports -> {config.NOAA_RSGA_CSV}")
