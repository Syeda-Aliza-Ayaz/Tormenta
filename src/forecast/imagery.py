"""Daily coronal-hole features from SDO/AIA 193 Å images (DECISIONS D-70). Experiment only; nothing live uses this.

For each day's 00:00 UTC image (data/raw/imagery/aia193/, from src/ingest/fetch_aia.py):
  ch_band_low   % of the low-latitude Earth-facing strip (|x| < 0.3 R, |y| < 0.5 R) covered by coronal holes
  ch_band       % of the whole Earth-facing strip covered
  ch_east       % of the incoming strip (-0.7 R < x < -0.3 R), which faces Earth in about 2–4 days
  ch_disk       % of the visible disk covered
  ch_dark       median brightness inside the holes relative to the disk median (lower = darker; 1 when none)

Coronal holes: pixels below 0.35 × the disk median after a 5-pixel median filter, opened with a 7×7 square and kept
only in regions of at least 300 pixels, which drops thin filaments. Same method as the one-year check (D-70).
Images with a non-zero quality flag or no exposure time are skipped (the day stays blank).

    python -m src.forecast.imagery            # builds reports/forecast/experiments/imagery/ch_features.csv
"""
import glob
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

from src import config

IMAGES = config.RAW_DIR / "imagery" / "aia193"
OUT = config.FORECAST_REPORTS_DIR / "experiments" / "imagery"
COLUMNS = ["ch_band_low", "ch_band", "ch_east", "ch_disk", "ch_dark"]


NRT_FLAG = 1 << 30            # set on near-real-time files; marks the processing stream, not a bad image


def usable(quality) -> bool:
    """Archive images need quality 0; near-real-time images carry only the NRT marker on top of that."""
    return (int(quality or 0) & ~NRT_FLAG) == 0


def features_from_file(path: str):
    """(date, features) for one image, or (date, None) when the image is not usable."""
    from astropy.io import fits
    from scipy import ndimage
    day = pd.Timestamp(os.path.basename(path)[3:11])
    try:
        with fits.open(path) as h:
            hd, img = h[1].header, h[1].data.astype(float)
    except Exception:                                   # noqa: BLE001 - a damaged file leaves the day blank
        return day, None
    if not usable(hd.get("QUALITY", 0)) or not hd.get("EXPTIME"):
        return day, None
    img = img / hd["EXPTIME"]
    ny, nx = img.shape
    cx, cy = hd["CRPIX1"] - 1, hd["CRPIX2"] - 1
    r = hd["RSUN_OBS"] / hd["CDELT1"]                    # solar radius in this image's pixels
    yy, xx = np.mgrid[0:ny, 0:nx]
    x, y = (xx - cx) / r, (yy - cy) / r
    disk = np.hypot(x, y) < 0.95
    med = np.median(img[disk])
    dark = disk & (ndimage.median_filter(img, 5) < 0.35 * med)
    dark = ndimage.binary_opening(dark, structure=np.ones((7, 7)))
    lab, n = ndimage.label(dark)
    sizes = ndimage.sum(dark, lab, range(1, n + 1)) if n else np.array([])
    ch = np.isin(lab, 1 + np.flatnonzero(sizes >= 300))
    band, low = disk & (np.abs(x) < 0.3), np.abs(y) < 0.5
    east = disk & (x < -0.3) & (x > -0.7)
    pct = lambda m, base: 100.0 * (ch & m).sum() / base.sum()  # noqa: E731
    return day, {"ch_band_low": pct(band & low, band & low), "ch_band": pct(band, band), "ch_east": pct(east, east),
                 "ch_disk": pct(disk, disk), "ch_dark": float(np.median(img[ch]) / med) if ch.any() else 1.0}


def build(workers: int = 6, last: str = None) -> pd.DataFrame:
    """Features for every image on disk up to `last` (default: before the test period; after the lock, D-76, the test
    period and the production window)."""
    files = sorted(glob.glob(str(IMAGES / "AIA*_0193.fits")))
    end = pd.Timestamp(last) if last else pd.Timestamp(f"{config.TEST_START_YEAR}-01-01") - pd.Timedelta(days=1)
    files = [f for f in files if pd.Timestamp(os.path.basename(f)[3:11]) <= end]
    print(f"coronal-hole features: {len(files)} images, {workers} workers", flush=True)
    rows, skipped, t0 = {}, 0, time.time()
    with ProcessPoolExecutor(workers) as pool:
        futures = [pool.submit(features_from_file, f) for f in files]
        for i, fut in enumerate(as_completed(futures), 1):
            day, feats = fut.result()
            if feats is None:
                skipped += 1
            else:
                rows[day] = feats
            if i % 100 == 0 or i == len(files):
                spent = time.time() - t0
                print(f"  [{i}/{len(files)}] {100 * i / len(files):.0f}% | elapsed {spent / 60:.1f} min | "
                      f"about {spent / i * (len(files) - i) / 60:.0f} min left | unusable {skipped}", flush=True)
    out = pd.DataFrame.from_dict(rows, orient="index")[COLUMNS].sort_index()
    out.index.name = "date"
    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "ch_features.csv", float_format="%.4f")
    print(f"saved {len(out)} days ({out.index.min().date()} -> {out.index.max().date()}), {skipped} unusable", flush=True)
    return out


def load() -> pd.DataFrame:
    return pd.read_csv(OUT / "ch_features.csv", parse_dates=["date"], index_col="date")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", default=None, help="last image day (default: before the test period)")
    build(last=ap.parse_args().last)
