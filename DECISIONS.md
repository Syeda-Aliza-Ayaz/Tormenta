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

### D-31 · HistGB, one model per lead day: tuned on train, passed its rule, joins the live log · 2026-11-10 · ✅
- **Decision:**
  - 14 HistGradientBoosting models (lead days 1–7 × Ap and max Kp), using the §5 features
    (`src/forecast/features.py`).
  - Tuning: 12 random settings, time-ordered 5-fold cross-validation on the **training years only**, on lead day 3
    as the representative. The best settings are used for all lead days.
  - **Rule written down before validation:** HistGB goes live only if its mean Ap skill against `trailing27`
    over lead days 1–7 is above 0.
- **Why:**
  - "Direct" models (one per lead day) don't feed on their own forecasts, so errors don't build up from day to day.
  - Tuning every lead day separately would cost 7× the time for little gain.
  - The rule had to exist before the result, so the validation result can't influence it.
- **Alternatives considered:**
  - Predicting log(1+Ap): **lost** on cross-validation (RMSE 13.99 vs 13.77 for raw Ap), so raw Ap is used.
    Fitting on log scale pulls forecasts toward typical values.
  - One "recursive" model fed its own forecasts.
- **Result / consequence:** **PASS, mean skill +0.179.** Validation 2017–2019:

  | Ap RMSE | day 1 | day 2 | day 3 | days 4–7 |
  |---|---|---|---|---|
  | **HistGB** | **6.34** | **7.08** | **7.08** | **7.07–7.09** |
  | NOAA | 6.90 | 7.35 | 7.74 | — |
  | trailing27 | 7.63 | 7.69 | 7.70 | 7.71–7.73 |

  - **HistGB beats NOAA's official forecast on days 1–3** (skill against trailing27: 0.31 / 0.15 / 0.16, vs
    NOAA's 0.19 / 0.09 / −0.01) and beats every baseline at every lead day.
  - Max Kp RMSE: 1.03 on day 1 and 1.14–1.15 after, vs 1.23–1.24 for trailing27.
  - **Which features matter** (permutation importance on validation, Ap):
    - day 1 is dominated by **yesterday's max Kp**, then yesterday's Ap and the 27-day recurrence;
    - day 7 is dominated by the **27-day recurrence window**, then the 54-day recurrence and the season.
    - This matches the physics: recent activity sets the next day, and the Sun's rotation sets the following week.
  - **Caveats:**
    - Validation is solar minimum (D-23).
    - **HistGB almost never warns of storms after day 1**: 17 of 91 storm days caught on day 1 (Heidke skill
      score 0.25), about 0 from day 2 on. Persistence and recurrence27 catch more, with many false alarms. This
      confirms D-22: storm warnings need the interval or a tuned threshold (day 6).
  - The production bundle (`models/forecast/histgb.joblib`, 4.4 MB) is fitted on the production window
    (1947-06 → 2019-12, D-27). Its settings are in `models/forecast/histgb_params.json`.

### D-32 · The training script must not save a model "from `__main__`" · 2026-11-10 · ✅
- **Decision:** `python -m src.forecast.gbm` now runs `main()` through the imported module. A regression test
  loads the committed production bundle the way the daily job does.
- **Why:** the first saved bundle recorded its class as `__main__.HistGBDirect`. It loaded fine inside the
  training run, but **would have crashed the daily job at 02:00**. Found by previewing tomorrow's issue before pushing.
- **Alternatives considered:** a separate training script that imports the class (an extra file to maintain).
- **Result / consequence:**
  - The bundle was re-saved, and the test passes.
  - `--reuse-params` re-saves without repeating the 5-minute tuning.
  - The validation result is identical (+0.179).

### D-33 · HistGB starts in the live log with the 11 Nov 02:00 issue, not today · 2026-11-10 · ✅
- **Decision:** don't add HistGB rows to today's issue (origin 9 Nov), which was issued at 07:07.
- **Why:** adding them now would mean issuing about 13 hours into its own day 1, and later than the baselines it
  is compared with. In the live log, every model in a comparison should be issued at the same time from the same data.
- **Alternatives considered:** append HistGB for origin 9 Nov now. The log would allow it (a new model is a new key).
- **Result / consequence:** from the 11 Nov issue on, HistGB is issued at 02:00 alongside the baselines. Preview
  for 10–16 Nov from data up to 9 Nov: Ap 10–11, max Kp about 3, close to NOAA's outlook for those days.

### D-34 · Daily workflow verified on GitHub (dry run) · 2026-11-10 · ✅
- **Decision:** after installing the GitHub CLI and logging in, ran `daily.yml` with `dry_run=true` (run 42778526940).
- **Result / consequence:**
  - Passed in 35 s: install, tests, GFZ + NOAA download, issue step.
  - It found origin 9 Nov already issued and added 0 rows (idempotent), and committed nothing (dry run).
  - GitHub warns that `actions/checkout@v4` and `actions/setup-python@v5` target Node 20 (being retired; forced
    onto Node 24, still working) and that `ubuntu-latest` is moving to Ubuntu 26. No action needed now; to check
    on day 10.

### D-35 · Six overnight schedule slots, because GitHub runs scheduled jobs hours late · 2026-11-12 · ⏳
- **Decision:**
  - `daily.yml` now has slots at 00:17, 01:17, 02:17, 03:17, 04:47 and 07:47 UTC, off the busy top of the hour.
  - Issuing is idempotent, so the first run that gets through issues the forecast and later runs only refresh
    scores and NOAA.
  - The app shows a note when an issue went out more than 3 hours into its first forecast day.
- **Why:**
  - GitHub doesn't guarantee schedule times. On 11 Nov, the 02:00 and 06:00 slots started at **08:38 and 13:55
    UTC**. On 12 Nov, neither had started by 06:46 UTC.
  - A late issue isn't leakage (the models use no data from that day), but day 1 becomes a shorter lead.
  - If both slots slipped far enough, a whole day could be missed.
  - GFZ updates its file at 23:41–23:48 UTC, so any slot after midnight UTC finds yesterday's data.
- **Alternatives considered:** an external scheduler calling `workflow_dispatch` (needs a token and another
  service); accepting the delay.
- **Result / consequence:**
  - Up to six bot runs a day; only runs with changes commit.
  - The 11 Nov issue (origin 10 Nov) went out 8.6 h into its day 1. Its `issued_at` is in the log, and the app
    shows it.
  - Pending: check over the next days whether the earlier slots get through.

### D-36 · Chart tooltip: one hover region for observed days, one for forecast days · 2026-11-12 · ✅
- **Decision:** the forecast chart's crosshair is split at the issue day. Past days list only the observed value;
  forecast days list only the series that have a value for every forecast day.
- **Why:** reported by HRK. One tooltip over all days listed every series, so past days showed `null` for HistGB
  and the other models, and forecast days showed `null` for the observed value.
- **Result / consequence:** checked on the generated chart: 0 empty values in either region, for both Ap and max
  Kp. The app runs without errors.

### D-37 · Editor workspace files ignored · 2026-11-12 · ✅
- **Decision:** `*.code-workspace` added to `.gitignore`.
- **Why:** `Tormenta.code-workspace` is a personal VS Code file, not part of the project.

### D-38 · What-if runs on the real last 3 days, so unedited live values equal the live tab · 2026-11-12 · ✅
- **Decision:**
  - The what-if tab has a "Past 3 days" choice: **Real (live data up to now)** or **Steady at these values**.
  - "Latest live values" fills the form from the live tab's own "Kp now" hour and selects Real. Only the fields
    the user changes replace that hour (`predict.predict_on_history`); the lags and 3–24 h averages keep the
    real solar wind.
  - Presets select Steady, because a made-up scenario has no real past.
  - The response curves use the same choice, so they pass through the headline number.
- **Why:**
  - Reported by HRK: the live tab showed Kp 1.2 while the what-if tab, with "Latest live values", showed 0.8.
    The same thing happened on 8 Nov (3.2 vs 2.2). The cause is the one recorded in `dev_notes/`: the what-if tab
    repeated the current hour for 72 hours and erased the real history behind the lag and average features.
  - **A second cause, found while fixing it:** "Latest live values" took the newest hour with complete data. That
    is often the hour *ahead* of the clock (the solar wind is measured about an hour before it reaches Earth),
    while the live tab reports the current hour. So the two tabs could even describe different hours.
- **Alternatives considered:** remove the "Latest live values" button (5 minutes, but the tabs can no longer be
  compared and the most useful starting point for experiments is lost).
- **Result / consequence:**
  - Checked in the app with live NOAA data (12 Nov 07:00 UTC): live tab **1.1**, what-if unedited **1.1**, with
    the caption "Unchanged live values: this is the live tab's nowcast for the same hour".
  - Bz −20 nT and |B| 25 nT on the real history give 5.1; the same values held steady for 3 days give 6.2. The
    CME preset switches to Steady and gives 7.2.
  - Display rounding (the form shows 2 decimals) is not counted as an edit.
  - `tests/test_whatif.py` (4 tests): unedited equals the live tab exactly; an edit changes only the current
    hour; the F10.7 override reaches the features; the rounding tolerance works.
  - If live data is unavailable, Real falls back to Steady with a warning.

### D-39 · ARIMA family: parameters fitted once, forecasts by Kalman filter with fixed parameters · 2026-11-12 · ✅
- **Decision:**
  - `src/forecast/arima.py` provides ARIMA, SARIMA (27-day season) and ARIMAX as statsmodels SARIMAX models,
    one per target.
  - Each model's parameters are estimated **once** on the training years.
  - To forecast, the Kalman filter runs over the daily series with those parameters fixed, always from the first
    day of the series. The 7-day forecast for every origin is projected from the filtered state at D in one
    vectorised step.
  - ARIMAX inputs:
    - Ap 27 days before the target day, which is already observed when the forecast is made;
    - the 81-day trailing F10.7 mean, carried forward from D (D-09).
  - The first weeks of a series have no inputs yet, so those days are treated as unobserved. They are not
    filled from later days.
- **Why:** refitting at each of about 1,100 validation origins would take hours for SARIMA (D-10). Starting the
  filter at a fixed day makes a forecast for D identical whether or not later data exists.
- **Alternatives considered:** refit per origin (too slow); statsmodels' own `forecast()` per origin (correct
  but about 1,100 separate filter runs).
- **Result / consequence:**
  - A test checks the vectorised forecast against statsmodels' own forecast: **identical** (to 1e-6) for ARIMA
    and ARIMAX, Ap and max Kp, at two origins.
  - The general no-future-data test passes for all three.
  - New pinned dependencies: `statsmodels==0.15.0`, `patsy==1.0.3`, `formulaic==1.2.2`, installed with the
    existing pins as constraints. NumPy, pandas, SciPy and scikit-learn are unchanged.

### D-40 · ARIMA orders chosen on the training years only · 2026-11-12 · ✅
- **Decision:**
  - Order by AIC over p∈{1,2,3}, d∈{0,1}, q∈{0,1,2} on 1947–2013 (log Ap): **ARIMA(3,0,1)**.
  - Seasonal part by AIC: **(1,0,1,27)**, chosen over (1,0,0,27).
  - Raw vs log Ap by forecast RMSE on 2014–2016, still inside the training years: **raw** (9.38 vs 9.61).
  - The same orders are used for max Kp. Settings are in `models/forecast/arima_settings.json`.
- **Why:** like HistGB (D-31), nothing about the model is chosen by looking at validation or test.
- **Result / consequence:**
  - **The 27-day season lowers AIC by about 430** (43,496 → 43,069): statistical evidence that the Sun's
    rotation is in the data.
  - Raw Ap beat log Ap again, as for HistGB.

### D-41 · Validation: ARIMAX passes; ARIMA and SARIMA fail the rule · 2026-11-12 · ✅
- **Decision:** the same rule as HistGB, fixed in advance: mean Ap skill against `trailing27` over lead days 1–7
  must be above 0.
- **Result / consequence** (validation 2017–2019, Ap RMSE):

  | | day 1 | day 2 | day 3 | days 4–7 | mean skill | rule |
  |---|---|---|---|---|---|---|
  | HistGB | **6.34** | **7.08** | **7.08** | **7.07–7.09** | +0.179 | pass (live since 11 Nov) |
  | **ARIMAX** | 6.88 | 7.57 | 7.62 | 7.63–7.64 | **+0.047** | **pass**: joins the live log |
  | ARIMA | 6.98 | 7.76 | 7.84 | 7.85 | −0.004 | fail |
  | SARIMA | 7.25 | 8.29 | 8.54 | 8.66–8.74 | −0.198 | fail |
  | NOAA | 6.90 | 7.35 | 7.74 | — | — | benchmark |
  | trailing27 | 7.63 | 7.69 | 7.70 | 7.71–7.73 | 0 | the bar |

  - All three are better than trailing27 on **day 1**; ARIMAX ties NOAA there (6.88 vs 6.90). After day 1 they
    fall back toward the long-term mean.
  - ARIMAX's 27-day recurrence input keeps it just above the bar.
  - On max Kp, all three beat trailing27 on day 1 only.
  - ARIMAX's production bundle is `models/forecast/arimax.joblib` (1.3 KB, parameters only), fitted on
    1947-06 → 2019-12. The daily job now issues 6 models in about 3 s.
  - ARIMA and SARIMA stay in the backtest and the scorecards, but are not issued live.

### D-42 · Why SARIMA had the best AIC but the worst forecasts · 2026-11-12 · ✅
- **Finding:** AIC measures how well the model predicts **one step ahead, in the training years**. Several days
  ahead, these models fall back toward the training-period mean:
  - **Ap averaged 13.9 over 1947–2016 but only 7.75 in the quiet 2017–2019 validation years.**
  - Mean over-forecast on validation:

    | model | day 1 | day 3 | day 7 |
    |---|---|---|---|
    | SARIMA | +2.35 | +3.96 | +4.35 |
    | ARIMA | +0.75 | +1.25 | +1.38 |
    | ARIMAX | +0.60 | +0.99 | +1.09 |
    | trailing27 | +0.09 | +0.11 | +0.13 |

  - SARIMA's seasonal terms add memory of the long-run level, so it is pulled up the most.
  - trailing27 tracks the current level and is almost unbiased.
- **Why it matters:**
  - For the report: a good in-sample fit criterion does not guarantee good multi-day forecasts when the activity
    level shifts. This is the solar-minimum validation issue (D-23) in action.
  - It also suggests a fix to try only if time allows: model the departure from the 81-day level rather than Ap
    itself.
- **Result / consequence:** no change to the rule or the selection, which were fixed in advance. Listed as future work.

### D-43 · "Recent hindcast": the live models scored on 1 Jul – 12 Nov 2026 · 2026-11-13 · ✅
- **Decision:** `python -m src.backtest --period recent` runs the **production models**, exactly as the daily job
  does, on every issue day from the day after GFZ's last definitive day (30 Jun 2026) to the newest published day.
  It is scored against GFZ's provisional and nowcast values, flagged as such, and NOAA's archived day 1–3
  forecasts are scored on the same days.
- **Why:**
  - HRK asked to use the existing data instead of waiting for the live log, which had only 3 scored days.
  - These days are in **neither validation nor test**, and every live model was trained on data up to 2019, so
    nothing is reused or leaked.
  - The test period (2020 → 30 Jun 2026) stays untouched until day 6 (D-08).
  - Each forecast uses data up to its origin only, the same code path as live.
- **Alternatives considered:** wait for the live log (weeks); score the test period now (would spend the one-time test).
- **Result / consequence** (135 target days, mean Ap 9.3, 16 storm days, maximum Ap 73; Ap RMSE):

  | | day 1 | day 2 | day 3 | days 4–7 |
  |---|---|---|---|---|
  | **HistGB** | **9.02** | **9.01** | **8.58** | **8.86–9.04** |
  | ARIMAX | 9.15 | 9.58 | 9.32 | 9.24–9.26 |
  | NOAA | 9.76 | 9.54 | 9.36 | — |
  | trailing27 | 9.36 | 9.38 | 9.27 | 9.23–9.31 |
  | climatology | 10.49 | 10.49 | 10.49 | 10.49 |
  | persistence | 11.38 | 13.87 | 13.80 | 12.6–13.6 |

  - **The validation result holds on unseen, more active days:** HistGB is best at every lead day and beats NOAA
    on days 1–3. Its skill against trailing27 is smaller than in validation (+0.05 to +0.14 vs +0.15 to +0.31).
  - **ARIMAX is only level with trailing27 here** (skill about 0 after day 1). It passed its rule narrowly
    (+0.047), and this is consistent with that.
  - Storms: HistGB catches 2 of 16 storm days on day 1 and none from day 3 on; recurrence27 catches 5. This
    confirms that storm warnings need their own rule (D-22, day 6).
  - **Limits:**
    - 135 days is useful but still modest, and errors on neighbouring days are correlated.
    - The observed values are provisional and may change slightly when GFZ finalises them.
  - The live log is still the only proof that forecasts were written before their days. The hindcast is issued in
    hindsight, even though it uses the same data limits.
  - Files: `reports/forecast/metrics/recent_leads.csv`, `recent_storms.csv`. Test:
    `test_recent_hindcast_stays_outside_validation_and_test`.

### D-44 · OMNI raw files restored locally; retrain tests run again · 2026-11-13 · ✅
- **Decision:** HRK copied the original OMNI subset (`omni2_UuPWjVIAYC.lst/.fmt`, 245,688 hours,
  1998-01-01 → 2026-01-10) into `data/raw/`. The hourly table was rebuilt with `build_hourly` + `check` +
  `save_processed`, **without** `src.preprocessing.main`, so the committed `data/f107_history.csv` wasn't
  overwritten by an older local GFZ copy.
- **Result / consequence:**
  - The 2 weekly-retrain guard tests (`tests/test_update.py`) run and pass locally again.
  - `test_omni_spdf.py::test_spdf_parser_against_real_2024_file` still skips here, because NASA SPDF can't be
    reached from this network (v1 #31). It runs on GitHub, which can reach SPDF.
  - `data/raw/` and `data/processed/` stay out of git, as before.

### D-45 · 80% ranges for every live model, from out-of-sample errors per lead day · 2026-11-13 · ✅
- **Decision:**
  - `src/forecast/intervals.py`: for each model, target and lead day, the 10th–90th percentile of its
    out-of-sample errors gives the 80% range.
    - Ap uses **log ratios**, log(1+obs) − log(1+forecast), so the range widens on active days and stays ≥ 0.
    - Max Kp uses plain differences, clipped to 0–9.
  - The same method for every model, so ranges are comparable.
  - The daily job writes the ranges into the log (`ap_lo/hi`, `kpmax_lo/hi`).
  - The app draws HistGB's range as a band (one band keeps the chart readable).
- **Why:**
  - A single number hides how uncertain a 7-day forecast is.
  - The same quantiles are the starting point for the storm-risk number (D-22, day 6).
  - A fixed ±X would be too wide on quiet days and too narrow in storms.
- **Alternatives considered:**
  - Quantile models per lead day (14 more HistGB fits, and nothing similar for ARIMA).
  - Each model's own theoretical interval (ARIMA has one, HistGB doesn't, so they wouldn't be comparable).
- **Calibration data, changed once:**
  - **First version:** validation 2017–2019 only. Checked on the 135 unseen recent days, coverage was **72–78%**
    (target 80%), because validation is the quietest part of the cycle (D-23).
  - **Final version:** errors from **2008–2016** (models fitted ≤ 2007, which includes the cycle-24 maximum) plus
    validation 2017–2019 (fitted ≤ 2016). This uses training-period years only; the recent days and the test
    period are untouched.
  - **Disclosure:** this change was made *after* seeing the recent coverage. The reason (validation is too quiet)
    was already documented in D-23. The test period will give the clean check on day 6.
- **Result / consequence** (coverage on the recent hindcast, 1 Jul – 12 Nov 2026, lead days 1–7):
  - HistGB Ap **81–83%**; HistGB max Kp 76–78%; ARIMAX Ap 73–79%; 27-day average about 80%.
  - Example (HistGB, day 1): forecast Ap 5 → 1.6–8.3; forecast Ap 30 → 12–47. Day 7 is slightly wider.
  - Files: `models/forecast/intervals.json`, `reports/forecast/metrics/recent_interval_coverage.csv`,
    `reports/forecast/calibration_forecasts.csv.gz` (the out-of-sample forecasts, reused for the storm rule).
  - Tests: `tests/test_intervals.py`, plus a daily-job test that issued rows carry the ranges.

### D-46 · Chronos-Bolt (pretrained transformer, zero-shot) fails its rule; kept as an offline comparison · 2026-11-13 · ✅
- **Decision:**
  - `src/forecast/chronos_model.py` wraps `amazon/chronos-bolt-small` (48M parameters), used **zero-shot**: no
    training on our data.
  - For each issue day it gets the last 512 days of Ap (and, separately, max Kp) up to that day, and forecasts
    7 days. The point forecast is the median.
  - The same rule as every model (D-31): mean Ap skill against trailing27 over lead days 1–7 on validation > 0.
  - It's an optional dependency (`requirements-chronos.txt`; CPU PyTorch 2.15.0, chronos-forecasting 2.3.2).
    The registry leaves it out wherever PyTorch isn't installed.
- **Why:**
  - The teacher listed transformers.
  - Training one from scratch on about 29k days would overfit (D-11), so we use a pretrained one: Amazon trained
    it with self-supervised learning on many time series, so our data size doesn't matter.
  - It also tests our own work: does a model with **no** physics features match HistGB?
- **Result / consequence:** **FAIL, mean skill −0.039.** Ap RMSE:

  | | day 1 | day 2 | day 3 | days 4–7 |
  |---|---|---|---|---|
  | HistGB | **6.34** | **7.08** | **7.08** | **7.07–7.09** |
  | ARIMAX | 6.88 | 7.57 | 7.62 | 7.63–7.64 |
  | **Chronos** | 7.21 | 7.95 | 8.00 | 7.91–7.97 |
  | trailing27 | 7.63 | 7.69 | 7.70 | 7.71–7.73 |

  - On max Kp, Chronos is level with ARIMAX (day 1: 1.11; HistGB 1.03).
  - On the recent hindcast (135 days): 9.24 on day 1 and 9.38–9.76 after, close to ARIMAX and slightly behind
    trailing27 after day 1.
  - **Interpretation:** a general pretrained transformer, given only the raw series, does about as well as ARIMA:
    good on day 1, smooth and mean-reverting after that.
    - It doesn't use the 27-day recurrence the way HistGB's hand-made features do. Example: for 16–17 Nov 2026,
      HistGB and NOAA forecast a rise from the 21–22 Oct activity, while Chronos stays flat at about 7.5.
    - **The physics-based features are what make HistGB the best model.**
  - **Not tried, on purpose:** using Chronos's mean instead of its median, or longer contexts. Tuning it on
    validation after seeing the result would break the "rule first" discipline. Listed as future work.
  - **Consequence for deployment:** Chronos is not issued live, so the daily job and Streamlit Cloud don't need
    PyTorch, and the Streamlit memory test planned for day 5 (D-14) is no longer needed. Its backtest forecasts
    are saved (`reports/forecast/chronos_*_forecasts.csv.gz`) for the scorecards and the report.
  - Practical numbers: first load 7 min (one-time 190 MB weights download), then 0.4 s per forecast and about
    16 s per 256 forecast days on CPU.

### D-47 · F10.7 flare spikes filtered in the forecaster too (bug fix); HistGB and ARIMAX retrained · 2026-11-13 · ✅
- **Problem:** the nowcaster removes flare-contaminated F10.7 days (> 2× the trailing 27-day median of earlier
  days), but the forecaster's features and ARIMAX's input used the raw value. 24 such days since 1947 (e.g.
  939 sfu on 2011-03-07, normally about 110). Each one shifts the 81-day mean for 81 days, so about 1,900
  feature-days were distorted.
- **Decision:** one shared function, `features.mask_flares`, used by the nowcaster (behaviour unchanged; its
  parity tests pass), the forecaster features and ARIMAX. Regression test:
  `test_flare_spike_does_not_reach_the_f107_features`.
- **Result / consequence:** retrained with the existing tuned settings, and the rules re-run:
  - HistGB **+0.177** (was +0.179): PASS.
  - ARIMAX **+0.046** (was +0.047): PASS.
  - ARIMA and SARIMA don't use F10.7 and are unchanged.
  - The 80% ranges were recalibrated: HistGB Ap coverage on the recent days is 81–83%.
  - The small change is expected: only 24 days were affected, and same-day F10.7 has low importance.

### D-48 · Storm classifier with rare-event thresholds (fix for the imbalance problem) · 2026-11-13 · ✅
- **Problem:** the regression models forecast typical values, so they almost never reach the storm line
  (max Kp ≥ 5−). On validation, HistGB caught 17 of 91 storm days on day 1 and none from day 3 on (D-22).
  Storm days are 8% of days in quiet years and 23% over 1947–2016.
- **Decision:** `src/forecast/storm.py`.
  - A HistGB **classifier** per lead day gives P(storm on D+h) from the same causal features. Its settings are
    fixed in advance, not tuned.
  - **No resampling,** so the probabilities stay honest. Imbalance is handled by the **decision threshold**:
    fit on data ≤ 2007, predict 2008–2016, and pick the threshold that maximises Heidke skill per lead day.
    Result: **0.21–0.29**, far below 0.5, as expected for rare events.
  - Validation (fit ≤ 2016) and the recent days are never used for any choice.
  - The production classifier (≤ 2019) is saved with its thresholds.
  - The daily job writes a separate **append-only** `forecasts/storm_log.csv` (the forecast log's columns stay
    unchanged), scored in `storm_scores.csv`.
  - The app shows "storm risk %" per day, with ⚠️ above the threshold.
- **Alternatives considered:**
  - Sample weighting (the nowcaster's `1 + Kp/3` didn't help there).
  - Oversampling (distorts the probabilities).
  - Thresholding the regression forecast (no probability to tune).
- **Result / consequence** (Heidke skill):

  | lead day | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
  |---|---|---|---|---|---|---|---|
  | **validation, storm warning** | **0.36** | **0.31** | **0.32** | **0.28** | **0.29** | **0.32** | **0.29** |
  | validation, best other model | 0.33 (persistence) | 0.19 (recurrence) | 0.19 | 0.19 | 0.19 | 0.19 | 0.19 |
  | recent, storm warning | **0.37** | **0.28** | **0.25** | 0.09 | 0.11 | 0.18 | 0.15 |
  | recent, recurrence | 0.22 | 0.22 | 0.22 | **0.22** | **0.22** | **0.22** | **0.22** |

  - It catches 30–46% of storm days at every lead day on validation, where HistGB caught 0–19%. The cost is
    false alarms: about 6 in 10 warnings are false. That's normal for rare-event warnings, and it's the trade-off
    the threshold makes.
  - **On the recent days, it is best on days 1–3. On days 4–7 the plain 27-day recurrence rule is better** (16
    storm days, a small sample). Kept as a finding; the test period will check it on day 6.
  - Tests: `tests/test_storm.py` (no future data, rare-event threshold, frozen bundle) and a daily-job test
    (append-only, idempotent storm log).

### D-49 · Storm confusion tables per lead day, every model · 2026-11-13 · ✅
- **Decision:** `python -m src.forecast.tables` writes `reports/forecast/storm_tables.md`: one table per lead day
  (1–7), for validation and the recent hindcast. Columns: caught, missed, false alarm, correct quiet, detection
  rate, false-alarm ratio, Heidke skill.
- **Why:** HRK asked for the confusion matrix of every model at each lead day.
- **Result / consequence:** NOAA isn't included, because its archived forecasts contain Ap only. Two generator
  glitches were fixed before publishing: a duplicated Chronos row and a "-0.00".

### D-50 · Code comments made impersonal · 2026-11-13 · ✅
- **Decision:** 14 comments and docstrings in 13 files were rewritten as neutral technical text: no hardware
  details, names, anecdotes, dated "checked on" notes, local time zones or first person. History stays in this
  log; code refers to it by decision ID.
- **Why:** HRK asked for professional code without personal remarks.
- **Result / consequence:** comments only; no code changed (all files compile, all tests pass). The app's author
  credit in the footer is kept.

### D-51 · Headline models fixed before the test period is scored · 2026-11-13 · ✅
- **Decision:** by the rule written in advance (PLAN §6: highest mean validation skill over lead days 1–7),
  the **headline value forecast is HistGB** (+0.177, vs ARIMAX +0.046, NOAA +0.091 over days 1–3 only). The
  **headline storm warning is the storm classifier** (D-48, Heidke 0.28–0.36 on validation).
- **Why:** this entry is committed *before* `python -m src.forecast.test_eval` runs, so the git history shows
  the choice wasn't influenced by the test result.
- **Result / consequence:** the test period (2020-01-01 → last definitive day) is scored once with the models as
  committed. A second run needs `--force` and a new DECISIONS entry.
