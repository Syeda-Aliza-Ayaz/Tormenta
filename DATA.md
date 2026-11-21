# Data sources

Every dataset the project uses, how it was collected, its licence and when it was accessed. Raw data are not
committed to git. They are downloaded by script:

```bat
python -m src.download_data                 &:: core: GFZ + OMNI -> daily and hourly tables (~5 min)
python -m src.download_data --all           &:: + solar images and experiment datasets (~3 h, ~7 GB)
```

No dataset contains personal data. NOAA's forecasts are used only as a benchmark, never as model inputs.

## Used by the deployed models

| Dataset | Content | Collection method | Licence / terms | Accessed | Size used |
|---|---|---|---|---|---|
| **GFZ Potsdam Kp, ap, Ap, F10.7** ([kp.gfz.de](https://kp.gfz.de)) | 3-hourly Kp and ap, daily Ap, observed F10.7, definitive flag, 1932 → | HTTPS download of `Kp_ap_Ap_SN_F107_since_1932.txt` (`src/ingest/fetch_gfz.py`); refreshed by the daily job | CC BY 4.0 (Matzka et al. 2021, doi:10.5880/Kp.0001). Sunspot numbers in the same file are CC BY-NC and are **not used** | first 2026-10-26; daily since 2026-11-10 | 34,653 days |
| **NASA OMNI2 hourly** ([omniweb.gsfc.nasa.gov](https://omniweb.gsfc.nasa.gov)) | solar wind at Earth's bow shock: \|B\|, Bx, By, Bz (GSM), speed, density, temperature, 1998 → | OMNIWeb subset (2026-10-26) for the first build; SPDF yearly files `omni2_YYYY.dat` over HTTPS since then (`src/ingest/fetch_omni.py`) | NASA public data, free use with acknowledgement of NASA/GSFC SPDF | 2026-10-26; SPDF refresh 2026-11-20 | 245,688 hours |
| **NOAA SWPC real-time solar wind** ([swpc.noaa.gov](https://www.swpc.noaa.gov)) | 1-minute propagated solar wind (7 days), F10.7, estimated Kp | JSON API, no key (`src/ingest/fetch_live.py`); hourly archive kept by the daily job (`src/ingest/sw_archive.py`) | US Government work, public domain | live; archive from 2026-11-12 | live inputs |
| **SDO/AIA 193 Å images** ([jsoc.stanford.edu](http://jsoc.stanford.edu)) | one 1024×1024 level-1.5 FITS image per day at 00:00 UTC, 2010-05-13 → | HTTPS from the JSOC synoptic archive (`src/ingest/fetch_aia.py`); near-real-time folder for live use (`src/ingest/aia_live.py`) | NASA SDO data policy: free and open; "Courtesy of NASA/SDO and the AIA science team" | 2026-11-20 to 2026-11-21; live daily since 2026-11-21 | 5,856 images (5,827 usable days) |

## Benchmarks and experiments (not model inputs of the deployed models)

| Dataset | Content | Collection method | Licence / terms | Accessed | Size used |
|---|---|---|---|---|---|
| **NOAA SWPC RSGA reports** | NOAA's daily forecasts: Ap for days 1–3, storm probabilities | FTP warehouse `ftp.swpc.noaa.gov/pub/warehouse/YYYY/YYYY_RSGA.tar.gz` (`src/ingest/fetch_noaa.py`, `src/forecast/experiments/noaa_storm.py`) | US Government work, public domain | 2026-11-10 (Ap), 2026-11-20 (storm probabilities) | 10,765 Ap forecasts, 2017 →; 1,090 days of storm probabilities |
| **NOAA SWPC 3-day forecast and 27-day outlook** | live forecasts | HTTPS text products, saved daily by the daily job | public domain | daily since 2026-11-10 | live benchmark |
| **NOAA SWPC event reports** | X-ray and optical flares, radio bursts, proton data, 1996–2019 | FTP warehouse `YYYY_events.tar.gz`, `YYYY_DPD.txt` (`src/ingest/fetch_events.py`) | public domain | 2026-11-20 | 48 files (experiment D-74, rejected) |
| **NASA DONKI CME catalogue** ([api.nasa.gov](https://api.nasa.gov)) | coronal mass ejections: speed, width, predicted arrival | REST API, 60-day windows; key from the `NASA_API_KEY` environment variable, never stored (`src/ingest/fetch_donki.py`) | NASA open data | 2026-11-18 | 10,386 CMEs, 2010-04 → 2026-11 (experiment D-67, rejected) |

## Derived tables

| File | Built from | Command |
|---|---|---|
| `data/processed/daily.csv` | GFZ | `python -m src.daily` |
| `data/processed/tormenta_hourly.csv` | OMNI + GFZ, one row per hour, each hour labelled with its 3-hour Kp | `python -m src.download_data` |
| `data/f107_history.csv` (committed) | GFZ observed F10.7 | rebuilt by the weekly job |
| `data/noaa_rsga_ap.csv` (committed) | NOAA RSGA | `python -m src.ingest.fetch_noaa --rsga 2017 <year>` |
| `reports/forecast/experiments/imagery/ch_features.csv` (committed) | AIA images | `python -m src.forecast.imagery --last <date>` |
| `forecasts/*.csv` (committed, append-only) | the daily job | `python -m src.issue` |

## Credits

NASA/GSFC Space Physics Data Facility OMNIWeb · GFZ German Research Centre for Geosciences (Kp, Ap, F10.7, CC BY 4.0)
· NOAA Space Weather Prediction Center · SDO/AIA data courtesy of NASA/SDO and the AIA science team, via the Stanford
JSOC · NASA CCMC DONKI.
