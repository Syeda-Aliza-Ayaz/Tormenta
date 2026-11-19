# Open work

Items that are blocked or deferred, mostly because a data source could not be reached when the check was made.
Remove an item only when it is done and recorded in [DECISIONS.md](DECISIONS.md).

## Blocked by network access (retry with a stable connection)

- [ ] **Older OMNI years.** The SPDF download of 1963–1997 was throttled (1.7 kB/s) and timed out; partial files
  sit in `data/raw/spdf`. Low priority: solar wind before 1998 is sparse anyway.
- [ ] **Install a netCDF reader** (`conda install -n tormenta xarray netcdf4`), needed for the DSCOVR files.

- [ ] **Real-time vs OMNI solar wind, measured on real data** (D-68 / D-69).
  The candidate `sw_rec_poisson` was validated on OMNI, a corrected archive. Live forecasts would read NOAA's
  real-time feed. A synthetic stress test stands in for now. The real check:
  - Download DSCOVR 1-minute data (`m1m` magnetometer, `f1m` Faraday cup) for 2017–2019 from NOAA NCEI
    (`https://www.ngdc.noaa.gov/dscovr/data/YYYY/MM/`). On 2026-11-19 the server timed out.
  - Reading the files needs a netCDF reader (`netCDF4` or `xarray`); neither is installed in the `tormenta` env.
  - Build the daily solar-wind summaries from DSCOVR. Compare them with OMNI day by day (bias, scatter, gaps).
    Then rerun the yearly validation with models fitted on OMNI and forecasts made from DSCOVR inputs.
- [ ] **NOAA SWPC live feed gap rate.** On 2026-11-19 a second try worked: the feed returned 166 hours (7 days).
  Still to do: record its gap rate from `forecasts/solar_wind_hourly.csv` after a few weeks of archiving.

## Needed before solar-wind features can go live

- [ ] **Archive the live solar wind daily: built, waiting for `main`.** `src/ingest/sw_archive.py` keeps the
  hourly feed in `forecasts/solar_wind_hourly.csv`, and `src/issue.py` calls it every run. It was seeded locally
  on 2026-11-19 (166 hours). It collects only once this code is on `main`, because the daily job runs there; each
  day of delay is a day of history lost, since the feed keeps 7 days. The echo needs days 19–27 before the issue
  day, so it is usable about 4 weeks after the archive starts. Until then, use the variant without the echo
  (`solar_wind` + Poisson loss). Check with `python -m src.ingest.sw_archive --status`.
- [ ] **OMNI lag.** The local OMNI hourly table ends 2026-01-10. Refresh it from SPDF
  (`OMNI_SPDF_URL` in `config.py`) before any refit that uses solar-wind features.
- [ ] **Rescale real-time inputs if biased** (D-69). Storm warnings lost Heidke skill under a 25% density bias.
  Fit the rescaling from the DSCOVR-vs-OMNI comparison above.
- [ ] **Shadow run: built, waiting for `main`** (D-69). `forecasts/shadow_log.csv` starts filling once `fixes` is
  merged. Score it against the live model after several weeks (the fallback to HistGB on `no_sw` days is built).

## Deployment

- [ ] **Merge `fixes` into `main`.** As of 2026-11-19, `fixes` is 7 commits ahead (D-59 bug fixes, D-63 refit,
  D-64, D-65 dashboard). The daily job runs from `main`, so the live log still uses the models fitted to
  2019-12-31.

## Measurement that needs time to pass

- [ ] **Real-time vs OMNI on our own archive.** The archive holds real-time data only and is never overwritten with
  OMNI. Once OMNI is refreshed past the archive's first day (2026-11-12), compare the two hour by hour: bias,
  scatter, gaps. This can replace or confirm the DSCOVR check above.

- [ ] **Final GFZ revision of the live period** (D-60). Rerun `python -m src.forecast.checks skew` once GFZ marks
  2026-07 onward as definitive.
- [ ] **Monitor retrain** (D-63). It is skipped until GFZ has 6 months of definitive data after 2026-06-30.
