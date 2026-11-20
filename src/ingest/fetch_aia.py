"""Daily SDO/AIA 193 Å images for the coronal-hole experiment (DECISIONS D-70).

One synoptic image per day at 00:00 UTC (1024×1024 FITS) from Stanford's public JSOC archive, kept in
data/raw/imagery/aia193/ (not committed). By default May 2010 – Dec 2019; after the lock (D-76) the test period
and the production window are fetched with --first/--last. Days already on disk are skipped, so a stopped run resumes where it left off; a file is saved only when it
is a valid FITS file. Progress (done / total, rate, time left) is printed every 25 files.

    python -m src.ingest.fetch_aia
    python -m src.ingest.fetch_aia --first 2020-01-01 --last 2026-06-30      # after the lock (D-76)
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

from src import config

DIR = config.RAW_DIR / "imagery" / "aia193"
URL = "https://jsoc1.stanford.edu/data/aia/synoptic/{d:%Y/%m/%d}/H0000/AIA{d:%Y%m%d}_0000_0193.fits"
FIRST, LAST = "2010-05-13", "2019-12-31"
WORKERS = 4


def _fetch(day: pd.Timestamp) -> str:
    path = DIR / f"AIA{day:%Y%m%d}_0000_0193.fits"
    for attempt in range(3):
        try:
            r = requests.get(URL.format(d=day), timeout=300)
            if r.status_code == 404:
                return "missing"
            r.raise_for_status()
            if not r.content.startswith(b"SIMPLE"):
                return "invalid"
            tmp = path.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(path)
            return "ok"
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return "failed"


def download(first: str = FIRST, last: str = LAST) -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    days = pd.date_range(first, last, freq="D")
    todo = [d for d in days if not (DIR / f"AIA{d:%Y%m%d}_0000_0193.fits").exists()]
    print(f"AIA 193: {len(days) - len(todo)} of {len(days)} days on disk, {len(todo)} to fetch", flush=True)
    counts, t0 = {"ok": 0, "missing": 0, "invalid": 0, "failed": 0}, time.time()
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(_fetch, d): d for d in todo}
        for i, f in enumerate(as_completed(futures), 1):
            counts[f.result()] += 1
            if i % 25 == 0 or i == len(todo):
                spent = time.time() - t0
                rate = i / spent * 3600
                print(f"  [{i}/{len(todo)}] {100 * i / len(todo):.0f}% | {rate:.0f} per hour | elapsed {spent / 60:.0f} min | "
                      f"about {(len(todo) - i) / (i / spent) / 60:.0f} min left | {counts}", flush=True)
    return counts


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", default=FIRST)
    ap.add_argument("--last", default=LAST)
    a = ap.parse_args()
    download(a.first, a.last)
