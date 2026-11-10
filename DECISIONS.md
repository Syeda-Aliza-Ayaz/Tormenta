# Tormenta: decision log

Every decision we make, why we made it, and what came of it. **Add an entry when a decision is made, and fill in
"Result" once we know it.** Never delete an entry: if a decision is reversed, add a new one that says which entry
it replaces.

Decisions 1–35 from the nowcaster build are in [TORMENTA_BUILD_PLAN.md §7](TORMENTA_BUILD_PLAN.md).
The entries below start the forecaster work (v2), planned in [PLAN.md](PLAN.md).

**Status:** ✅ adopted, result known · ⏳ adopted, result pending · 🔁 replaced (see the entry it points to) · ❌ tried and rejected

Template:

```
### D-NN · Title · YYYY-MM-DD · status
- **Decision:**
- **Why:**
- **Alternatives considered:**
- **Result / consequence:**
```

---

### D-01 · Turn the project into a forecaster with at least 7 days ahead · 2026-11-10 · ⏳
- **Decision:** forecast geomagnetic activity for lead days 1–7, then score the forecasts against official data.
- **Why:** the teacher required it.
- **Alternatives considered:** none; this is a requirement.
- **Result / consequence:** the nowcaster's solar-wind inputs are only useful about 1 hour ahead (the L1 → Earth
  transit), so they cannot drive a multi-day forecast. This forces D-02 and D-03.

### D-02 · Allow Kp/Ap as inputs, for the forecaster only · 2026-11-10 · ⏳
- **Decision:** use past Kp/Ap (autoregression and the 27-day recurrence) as forecaster inputs. The nowcaster
  keeps its "no geomagnetic indices" rule (v1 #17).
- **Why:** nobody knows the solar wind days ahead. Beyond about 1 day, the only information available is past
  activity, the 27-day solar rotation and the solar cycle.
- **Alternatives considered:** keep solar-wind inputs only, which would give no skill beyond day 1.
- **Result / consequence:** persistence and 27-day recurrence become the baselines we must beat.

### D-03 · Target: daily Ap and daily max Kp, lead days 1–7 · 2026-11-10 · ⏳
- **Decision:** forecast daily values, not 3-hourly Kp.
- **Why:**
  - These are the quantities NOAA forecasts, so we can compare with the official forecast directly.
  - Daily series suit ARIMA/SARIMA.
  - 3-hourly Kp over 7 days means 56 noisy steps.
- **Alternatives considered:** 3-hourly Kp for days 1–7; 3-hourly for days 1–3 and daily after that.
- **Result / consequence:** pending.

### D-04 · Keep the nowcaster as hour 0 and as its own app tab · 2026-11-10 · ⏳
- **Decision:** no rework of the nowcaster. It stays in the app next to the forecaster.
- **Why:** it is finished, tested and strong, and it shows the contrast between seeing the solar wind and forecasting blind.
- **Alternatives considered:** replace the project entirely.
- **Result / consequence:** pending.

### D-05 · No new input data sources: GFZ daily file is enough · 2026-11-10 · ✅
- **Decision:** train, forecast and verify from the GFZ file we already use
  (`Kp_ap_Ap_SN_F107_since_1932.txt`).
- **Why:**
  - It has 3-hourly Kp, daily Ap and F10.7 from 1932, about 8 solar cycles.
  - **Checked 10 Nov 2026:** it is updated daily (its last row was 9 Nov). Each row has a flag:
    2 = definitive (up to about Jun 2026), 1 = provisional, 0 = nowcast.
- **Alternatives considered:** adding OMNI solar wind as daily inputs. It stays a later ablation only, because it
  is expected to help only day 1.
- **Result / consequence:**
  - The loader must keep the `Ap` column (it currently drops it) and add daily max Kp.
  - The weekly "no new data" results were about OMNI, which lags by months, not GFZ.

### D-06 · NOAA as a benchmark only; days 1–3 from the archive, days 4–7 from now on · 2026-11-10 · ✅
- **Decision:** compare against NOAA's forecasts, and never use them as model inputs.
  - For days 1–3: the daily RSGA reports archived on SWPC's FTP server, line `Predicted Afr/Ap`.
  - For days 1–7: the 27-day outlook, saved daily from now on.
- **Why:** scoring ourselves against the official forecast is the strongest possible scorecard. Using NOAA as an
  input would make our skill borrowed.
- **Alternatives considered:** no official benchmark (weak); NOAA's F10.7 forecast as an ARIMAX input (makes the
  model depend on NOAA).
- **Result / consequence:**
  - **Checked 10 Nov 2026:** the archive has RSGA reports for every year, about 364 per year. The 27-day outlook
    is **not** archived.
  - So the comparison with NOAA for days 4–7 covers only the days after we start saving.

### D-07 · Evaluation: backtest for the evidence, live log for the demonstration · 2026-11-10 · ⏳
- **Decision:**
  - A rolling-origin backtest (one forecast per day over validation and test) is the main evidence.
  - In parallel, an append-only live log scored against GFZ.
- **Why:** a 7-day forecast takes 7 days to verify. By the deadline the live log will hold only about a week of
  verified forecasts, far too few for statistics.
- **Alternatives considered:** live verification only.
- **Result / consequence:** the live log can never be backfilled; past dates belong to the backtest. A test
  enforces this.

### D-08 · Same split years, history extended back to 1932 · 2026-11-10 · ⏳
- **Decision:**
  - train 1932–2016
  - validation 2017–2019
  - test 2020 → last definitive day
- **Why:** the boundaries match the nowcaster, so results are comparable. The extra history adds solar cycles,
  which matters for the 27-day and solar-cycle effects.
- **Alternatives considered:** train from 1998, as the nowcaster does.
- **Result / consequence:** pending.

### D-09 · ARIMAX exogenous inputs are never future values · 2026-11-10 · ⏳
- **Decision:** F10.7 for D+1..D+7 is the last known value carried forward, in both the backtest and live.
- **Why:** ARIMAX needs the exogenous inputs for the forecast days too. Using the real future values in the
  backtest would be leakage that can't be reproduced live.
- **Alternatives considered:** NOAA's F10.7 forecast (rejected by D-06).
- **Result / consequence:** pending.

### D-10 · SARIMA: fit once, then update with new data at each forecast date · 2026-11-10 · ⏳
- **Decision:** fit SARIMA (27-day season) on train once. At each backtest origin, feed in the new observations
  without re-estimating the parameters.
- **Why:** refitting a 27-day seasonal model for about 2,500 backtest origins is too slow for our timeline.
- **Alternatives considered:** refit at every origin (too slow); refit weekly (fallback).
- **Result / consequence:** pending.

### D-11 · Transformer = Chronos-Bolt used as-is, not one we train · 2026-11-10 · ⏳
- **Decision:** use the pretrained Chronos-Bolt time-series transformer without training it. Training our own
  transformer is dropped unless everything else is done.
- **Why:** 1.5 weeks; our dataset is small for training a transformer (about 34k daily rows); the teacher listed
  transformers as an option.
- **Alternatives considered:** train a small transformer ourselves.
- **Result / consequence:** pending.

### D-12 · Retrain only when performance drops · 2026-11-10 · ⏳
- **Decision:** a weekly monitor computes the 28-day rolling skill score against persistence (lead days 1–3) from
  the live scores.
  - Two degraded checks in a row trigger a retrain.
  - The existing gate still decides promotion.
  - The reason for each retrain is logged.
- **Why:**
  - The teacher's rule.
  - The current setup retrains on a schedule whenever there is new data, and never asks whether the current model
    is actually doing badly.
  - Skill rather than raw RMSE, because raw error jumps in every storm even when the model is fine.
- **Alternatives considered:** a raw RMSE threshold (fires on every storm); keep the weekly scheduled retrain.
- **Result / consequence:** the degradation margin is set from the backtest. For the remaining weeks the monitor
  will most likely report "healthy", so the trigger is shown with a test that injects degraded scores.

### D-13 · Daily data cadence: daily GitHub Actions job · 2026-11-10 · ⏳
- **Decision:** a new daily job (about 02:00 UTC) downloads GFZ, issues forecasts, saves NOAA products, scores
  old forecasts and commits.
- **Why:** a daily forecast needs daily inputs and daily verification. The weekly job is too slow.
- **Alternatives considered:** keep weekly.
- **Result / consequence:**
  - One small bot commit per day.
  - Streamlit Cloud redeploys on each commit, causing a short outage early in the morning (Pakistan time).

### D-14 · Deployment: Streamlit Cloud runs the full forecaster; HF static Space in the browser · 2026-11-10 · ⏳
- **Decision:**
  - **Streamlit Cloud:** the full app, with every model forecasting live from the teacher's inputs. Chronos runs
    live if the CPU-only torch build fits; otherwise the app shows Chronos's saved daily forecast.
  - **HF static Space:** the same app in the browser (stlite), with Chronos's saved forecast only.
  - **HF model repo:** models and model card.
  - **Flask:** local, plus a forecast endpoint.
- **Why:**
  - Deployment is required.
  - Hosted HF Spaces need PRO (v1 #30).
  - Streamlit Cloud gives 1 GB of memory guaranteed and about 2.7 GB at most, which is enough to try CPU torch.
- **Alternatives considered:** Chronos only in the daily job, which would not be interactive.
- **Result / consequence:** the Chronos-on-Streamlit test is on day 5. Every app must handle an unavailable
  model without crashing.

### D-15 · Deploy early · 2026-11-10 · ⏳
- **Decision:** a basic forecast tab goes live on day 2; every later step redeploys.
- **Why:** finding deployment problems on the last day is the biggest risk to a "must" requirement.
- **Alternatives considered:** deploy everything at the end.
- **Result / consequence:** pending.

### D-16 · Snapshot the nowcaster on a branch; new work goes directly to `main` · 2026-11-10 · ✅
- **Decision:** created and pushed the branch `nowcaster` at `2d8e3e8` (the bot's weekly update, 9 Nov). New work
  is committed straight to `main`.
- **Why:** keeps a complete, working copy of the nowcaster project, safe from the forecaster changes.
- **Alternatives considered:** a feature branch for the forecaster (rejected: the team wants to work on `main`);
  a tag (optional extra).
- **Result / consequence:**
  - Streamlit Cloud deploys from `main`, so every push changes the live app. **Run the tests before every push.**
  - Scheduled workflows run only on the default branch, so the snapshot won't retrain. That is intended.

### D-17 · Defer the repository cleanup to the last day · 2026-11-10 · ⏳
- **Decision:** leave the duplicate files alone until day 10.
- **Why:** a check on 10 Nov found 18 byte-identical file pairs, mostly `reports/v2/` vs `reports/figures` and
  `reports/metrics`, plus copies in `docs/report/figs`. There are also 5 model files (17 MB) and 2 zips. All of it
  is clutter, and none of it breaks anything. `reports/` will change anyway during the forecaster work.
- **Alternatives considered:** clean now.
- **Result / consequence:** pending.

### D-18 · New plan file; the old plan is kept as the record · 2026-11-10 · ✅
- **Decision:** the forecaster plan lives in `PLAN.md`. `TORMENTA_BUILD_PLAN.md` gets a pointer line and is
  otherwise left as the nowcaster's record. Decisions are logged here.
- **Why:** the old plan documents decisions that are still true for the nowcaster, so rewriting it would lose that history.
- **Alternatives considered:** edit the old plan in place.
- **Result / consequence:** done.

### D-19 · Forecaster history starts 1947-06-01, not 1932 · 2026-11-10 · ✅ (replaces the 1932 start in D-08)
- **Decision:** all forecasters train from 1947-06-01 to 2016-12-31. The validation and test years are unchanged.
- **Why:** the GFZ file's F10.7 starts on 1947-02-14, so the 81-day trailing mean exists from about May 1947.
  Starting every model on the same day keeps the comparison fair (ARIMA could use 1932, but HistGB with F10.7 could not).
- **Alternatives considered:** Ap-only models from 1932 and the rest from 1947, which would make an unequal comparison.
- **Result / consequence:** about 25,000 training days (7 solar cycles) instead of 31,000. Kp and Ap themselves have
  no gaps from 1932 (checked: 34,647 days, no missing days, no missing Kp or Ap).

### D-20 · How NOAA forecasts line up with ours: origin = UTC date of (issue time − 3 h) · 2026-11-10 · ✅
- **Decision:** a NOAA product's "origin" is the last day whose data NOAA had (almost) complete.
  - The RSGA report, issued at 22:00 on D, has origin D and covers D+1..D+3 as lead days 1–3.
  - The 27-day outlook, issued at 02:58 on D, has origin D−1 (its first row, day D, is lead day 1).
  - The 3-day forecast, issued at 00:30 on D, has origin D−1.
  - Our forecast, issued at about 02:00 on D+1, has origin D.
- **Why:** comparing "lead day 1" with "lead day 1" is only fair if both forecasts knew the same data. NOAA's
  RSGA report misses the last 2–3 hours of day D, which is close enough and slightly in our favour. NOAA can see
  solar images (CMEs), which we can't. Both points are noted for the report.
- **Alternatives considered:** take the issue date as the origin, which would give the 27-day outlook a lead day 0
  and the RSGA report an extra day of advantage.
- **Result / consequence:** one rule in `src/ingest/fetch_noaa.py`, used for every NOAA product.

### D-21 · Baselines: persistence, 27-day recurrence, 27-day trailing mean, monthly climatology · 2026-11-10 · ✅
- **Decision:** four reference forecasts. `trailing27` (the mean of the last 27 days) was added to the plan's three.
- **Why:** an average over one solar rotation is a cheap measure of the current activity level. Any model that
  can't beat it is not learning anything beyond "how active has it been lately".
- **Alternatives considered:** the plan's three baselines only.
- **Result / consequence** (validation 2017–2019, 1,095 target days per lead day, `reports/forecast/metrics/`):

  | Ap RMSE | day 1 | day 2 | day 3 | day 7 |
  |---|---|---|---|---|
  | persistence | 8.20 | 10.22 | 10.72 | 10.77 |
  | recurrence27 | 8.99 | 8.99 | 8.99 | 8.99 |
  | **trailing27** | **7.63** | **7.69** | **7.70** | **7.72** |
  | climatology | 9.91 | 9.91 | 9.91 | 9.91 |

  - **trailing27 is the strongest baseline at every lead day, even day 1.** Its skill against climatology is +0.40.
    This is now the main bar the real models must clear.
  - Persistence beats climatology only on day 1. By day 3 it is worse than climatology (skill −0.17).
  - Storm days (max Kp ≥ 5−, 91 of 1,095):
    - persistence detects 38% on day 1 (Heidke skill score 0.33), then about 0 by day 3;
    - recurrence27 stays flat at Heidke skill score 0.19 at every lead day;
    - forecasts that are averages (trailing27, climatology) **never** reach the storm threshold. See D-22.
  - Max Kp shows the same ranking (day-1 RMSE: trailing27 1.23, persistence 1.26).

### D-22 · Storm warnings need more than a point forecast · 2026-11-10 · ⏳
- **Decision:** to be made on day 6. The options are to warn when the upper end of the 80% interval reaches 5−,
  or to tune a warning threshold on validation.
- **Why:** forecasts of an average are pulled toward typical values, so they almost never cross the storm
  threshold. D-21 shows this: trailing27 has zero hits.
- **Result / consequence:** pending.

### D-23 · Validation years are solar minimum: watch for a mismatch with test · 2026-11-10 · ⏳
- **Decision:** keep the split (D-08), and report it as a known limitation.
- **Why:** 2017–2019 was the quiet end of cycle 24, while the 2020+ test years cover the rise and peak of cycle 25.
  Monthly climatology, fitted on 1947–2016, overestimates the quiet years. A model chosen on validation is chosen
  on quiet conditions.
- **Alternatives considered:** move the validation years. Rejected: the boundaries would no longer match the
  nowcaster, and the test set must not change after this point.
- **Result / consequence:** pending. We will compare validation and test skill on day 6.

### D-24 · Plain ASCII in console output · 2026-11-10 · ✅
- **Decision:** new scripts print `->` instead of `→`.
- **Why:** the Windows console (cp1252) raised `UnicodeEncodeError` on `→`. GitHub Actions (UTF-8) never showed
  this, but anyone running the scripts locally on Windows would hit it.
- **Result / consequence:** the existing scripts still print `→`. Run them with `PYTHONUTF8=1` on Windows, or fix
  them when they are next touched.

### D-25 · NOAA's archived forecasts backfilled; NOAA is the bar for days 1–3 · 2026-11-10 · ✅
- **Decision:**
  - Backfill NOAA's predicted Ap for days 1–3 from the RSGA reports for 2017–2026, into the committed
    `data/noaa_rsga_ap.csv`: 3,591 reports, 10,765 rows, 524 KB.
  - Score them as model `noaa` in every backtest.
- **Why:** this is the official forecast scored on exactly our days, which makes it the strongest benchmark for the scorecard.
- **Problems hit, and the fixes:**
  - **An FTP timeout on the 2023 archive lost the whole first run**, because results were written only at the end.
    Now each year retries up to 3 times on a fresh connection and is cached in `data/raw/noaa_rsga/<year>.csv`
    as soon as it finishes.
  - **The 28 Feb 2020 report failed to parse.** It forecasts 29 Feb, and the year-guessing code tried "29 Feb 2019",
    which doesn't exist. Fixed, with a regression test.
  - 10 reports, issued just after midnight, give a "lead 0/−1" day. They fall outside lead days 1–3 and are dropped.
  - 2024 has 367 reports for 366 days, so NOAA sometimes reissues a report. The latest report per origin is kept.
- **Result / consequence** (validation 2017–2019, Ap RMSE, about 1,090 days per lead day):

  | | day 1 | day 2 | day 3 |
  |---|---|---|---|
  | **NOAA** | **6.90** | **7.35** | 7.74 |
  | trailing27 (best baseline) | 7.63 | 7.69 | **7.70** |
  | persistence | 8.20 | 10.22 | 10.72 |

  - NOAA's skill against climatology is +0.52 on day 1, +0.45 on day 2 and +0.39 on day 3.
  - **By day 3, NOAA is no better than the 27-day average.** For days 1–2, NOAA is the bar to beat. From day 3
    on, the realistic goal is to beat trailing27.

### D-26 · Daily job: 02:00 UTC with a 06:00 backup; issue only from yesterday; never backfill · 2026-11-10 · ⏳
- **Decision:** `.github/workflows/daily.yml` runs `src/issue.py` at 02:00 UTC (07:00 PKT) and again at 06:00
  UTC. A forecast is issued only when GFZ's newest complete day is yesterday. Issuing is idempotent: a second
  run on the same day adds nothing.
- **Why:**
  - **Checked 10 Nov:** GFZ's daily file was last modified at 23:48 UTC on 9 Nov, so yesterday's row is there by
    02:00. The 06:00 run covers a late GFZ update or a delayed GitHub cron.
  - If GFZ is more than a day behind, the job issues nothing. A late forecast would already overlap its own
    day 1, and filling the gap afterwards would amount to a backtest, not a live forecast (D-07).
- **Alternatives considered:** a single run (one GFZ delay loses a day); issuing from whatever day is newest
  (late forecasts would look better than they are).
- **Result / consequence:**
  - The log has one fixed set of columns from the start, including empty interval columns (`ap_lo/hi`,
    `kpmax_lo/hi`) for the trained models that come later.
  - `scores.csv` is rebuilt from the log every run, so it updates by itself when GFZ's provisional values
    become definitive.
  - NOAA failures are only warnings, because NOAA is a benchmark.

### D-27 · Live models are fitted on a fixed window (train + validation) · 2026-11-10 · ✅
- **Decision:** the daily job fits each model on definitive days from 1947-06-01 to 2019-12-31, the same data
  every day.
- **Why:**
  - A forecast changes only when its inputs change, never because the model quietly drifted.
  - It fits the "retrain only when performance drops" rule (D-12): a model changes only through the retrain path.
  - Trained models (from day 3 on) will be loaded from saved files rather than refitted each day.
- **Alternatives considered:** refit on all definitive data every day (drifts monthly, against D-12).
- **Result / consequence:** for the baselines, only climatology uses the fit at all.

### D-28 · First live forecast issued by hand, 10 Nov 07:07 UTC · 2026-11-10 · ✅
- **Decision:** ran `python -m src.issue` locally once, so the log starts today instead of tomorrow. Origin
  9 Nov (GFZ nowcast values); 4 models × 7 lead days = 28 rows. NOAA's 27-day outlook and 3-day forecast were
  saved with it.
- **Why:** every day of delay is a day of verified live results we won't have at the deadline (PLAN §8).
- **Result / consequence:**
  - **Note for the report:** this first issue came 7 hours into its own day 1 (10 Nov). The models use no data
    from 10 Nov, so nothing leaks, but its day 1 is strictly about 0.7 days ahead.
  - From 11 Nov on, forecasts are issued at 02:00 by the bot.
  - `issued_at` is recorded on every row, so this stays visible.

### D-29 · The app reads the committed forecast files; the forecast tab comes first · 2026-11-10 · ✅
- **Decision:**
  - The new "📅 7-day forecast" tab (first tab) reads `forecasts/*.csv` from the repo. It shows the last 30 days
    observed, every model's forecast and NOAA's outlook, plus a forecast table and an error-by-lead-day table
    once scores exist.
  - The daily job writes `forecasts/recent.csv` (last 60 days observed), so the app never calls GFZ.
- **Why:**
  - GFZ blocks browser requests (no CORS header), so the HF browser Space couldn't fetch it.
  - Reading files is also faster and can't fail.
  - Streamlit Cloud redeploys on each daily commit, so the files are always current there.
- **Result / consequence:**
  - The HF Space also gets the files (added to `SPACE_ASSETS`), but it is only republished weekly, so it can
    show a forecast up to a week old. The issue date is shown above the chart.
  - A daily HF sync is planned for day 8.
  - Chart colours: categorical slots 1–5 of the reference palette, fixed per series. They could not be
    re-validated here (Node.js isn't installed); they are the reference set, used in order.

### D-30 · File paths resolved at call time in `src/issue.py` · 2026-11-10 · ✅
- **Decision:** `load_log()` and `load_noaa_live()` look up `config.FORECAST_LOG` and `config.NOAA_LIVE_CSV` when
  called, not as default arguments.
- **Why:** a default argument is fixed when the module is imported. Tests that point `config` at a temporary
  folder would have read and overwritten the **real** `forecasts/log.csv`. This was caught while writing the
  tests, before any real log existed.
- **Result / consequence:** the tests use temporary folders only. A separate test checks that the committed
  log's rows are never changed.
