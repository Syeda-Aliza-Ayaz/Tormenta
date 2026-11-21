"""Download every dataset the project uses and rebuild data/ from scratch. Raw data are not committed to git.

    python -m src.download_data                  core data: GFZ + OMNI -> daily and hourly tables (~5 min, ~120 MB)
    python -m src.download_data --images         + SDO/AIA 193 Å images and coronal-hole features (~3 h, ~7 GB)
    python -m src.download_data --experiments    + NOAA event reports, NOAA RSGA storm forecasts, NASA DONKI CMEs
    python -m src.download_data --all            everything above

Each step is skipped if its output already exists; downloads resume where they stopped. Data sources, licences and
collection methods are documented in DATA.md.

Group      Step                        Source                                  Output
core       GFZ Kp/Ap/F10.7             kp.gfz.de (HTTPS)                       data/raw/Kp_ap_Ap_SN_F107_since_1932.txt
           daily table                 built from GFZ                          data/processed/daily.csv
           OMNI2 hourly solar wind     spdf.gsfc.nasa.gov yearly files (HTTPS) data/raw/spdf/omni2_YYYY.dat
           hourly table                built from OMNI + GFZ                   data/processed/tormenta_hourly.csv
images     SDO/AIA 193 Å, 1 per day    jsoc1.stanford.edu synoptic (HTTPS)     data/raw/imagery/aia193/
           coronal-hole features       built from the images                   reports/.../imagery/ch_features.csv
experiments NOAA event reports          ftp.swpc.noaa.gov warehouse (FTP)       data/raw/noaa_events/
           NOAA RSGA storm forecasts   ftp.swpc.noaa.gov warehouse (FTP)       data/raw/noaa_rsga_raw/
           NASA DONKI CME catalogue    api.nasa.gov (needs NASA_API_KEY)        data/raw/donki_cme/

Committed small tables (not re-downloaded here): data/f107_history.csv, data/noaa_rsga_ap.csv (NOAA's Ap forecasts,
rebuilt with `python -m src.ingest.fetch_noaa --rsga 2017 <year>`).
"""
import argparse
import os
import time
from datetime import datetime, timezone

T0 = time.time()


def step(i: int, n: int, msg: str) -> None:
    print(f"[{i}/{n}] {msg} | elapsed {(time.time() - T0) / 60:.1f} min", flush=True)


def core(i0: int, n: int) -> int:
    from src import config, daily
    from src.ingest import fetch_omni
    from src.ingest.fetch_gfz import load_gfz_daily
    from src.preprocessing import build_hourly, check, save_processed

    step(i0, n, "GFZ Kp/Ap/F10.7 -> daily table")
    daily.main(download=True)

    years = list(range(1998, datetime.now(timezone.utc).year + 1))
    step(i0 + 1, n, f"NASA OMNI2 hourly solar wind, {years[0]}-{years[-1]} ({len(years)} yearly files)")
    t = time.time()
    for k, year in enumerate(years, 1):
        path = fetch_omni.SPDF_DIR / f"omni2_{year}.dat"
        if not path.exists() or year >= years[-1] - 1:          # the last two years are still being updated
            try:
                fetch_omni.download_spdf_year(year)
            except Exception as exc:                             # the current year's file may not exist yet
                if year != years[-1]:
                    raise
                print(f"  {year}: not published yet ({type(exc).__name__})", flush=True)
        spent = time.time() - t
        print(f"  [{k}/{len(years)}] {year} | {spent / 60:.1f} min | about {spent / k * (len(years) - k) / 60:.0f} min left",
              flush=True)
    available = [y for y in years if (fetch_omni.SPDF_DIR / f"omni2_{y}.dat").exists()]

    step(i0 + 2, n, "hourly modelling table (OMNI + GFZ)")
    df = build_hourly(fetch_omni.load_omni_spdf(available[0], available[-1], download=False), load_gfz_daily())
    check(df)
    save_processed(df)
    print(f"  saved {config.PROCESSED_CSV} ({len(df):,} hours)", flush=True)
    return i0 + 3


def images(i0: int, n: int, first: str, last: str) -> int:
    from src.forecast import imagery
    from src.ingest import fetch_aia

    step(i0, n, f"SDO/AIA 193 Å images {first} -> {last} (one per day)")
    print(f"  {fetch_aia.download(first, last)}", flush=True)
    step(i0 + 1, n, "coronal-hole features from the images")
    imagery.build(last=last)
    return i0 + 2


def experiments(i0: int, n: int) -> int:
    from src.forecast.experiments import noaa_storm
    from src.ingest import fetch_donki, fetch_events

    step(i0, n, "NOAA SWPC event reports (flares, radio bursts, protons), 1996-2019")
    fetch_events.download()
    step(i0 + 1, n, "NOAA RSGA storm-probability forecasts, 2017-2019")
    for year in noaa_storm.YEARS:
        print(f"  {noaa_storm.download(year)}", flush=True)
    step(i0 + 2, n, "NASA DONKI CME catalogue")
    if os.environ.get("NASA_API_KEY"):
        print(f"  downloaded {fetch_donki.download()} windows; {len(fetch_donki.build_table()):,} CMEs", flush=True)
    else:
        print("  skipped: set the NASA_API_KEY environment variable (free key from api.nasa.gov)", flush=True)
    return i0 + 3


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--images", action="store_true", help="also download the AIA images (~7 GB)")
    p.add_argument("--experiments", action="store_true", help="also download the experiment-only datasets")
    p.add_argument("--all", action="store_true", help="core + images + experiments")
    p.add_argument("--first", default="2010-05-13", help="first image day (default: first AIA synoptic image)")
    p.add_argument("--last", default="2026-06-30", help="last image day")
    a = p.parse_args()
    want_images, want_exp = a.images or a.all, a.experiments or a.all
    n = 3 + 2 * want_images + 3 * want_exp
    i = core(1, n)
    if want_images:
        i = images(i, n, a.first, a.last)
    if want_exp:
        experiments(i, n)
    print(f"done: {n} steps in {(time.time() - T0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
