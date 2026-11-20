# Tormenta: decision log

Every decision we make, why we made it, and what came of it. **Add an entry when a decision is made, and fill in
"Result" once we know it.** Never delete an entry: if a decision is reversed, add a new one that says which entry
it replaces.

Decisions 1–35 from the nowcaster build are in [docs/plans/TORMENTA_BUILD_PLAN.md §7](docs/plans/TORMENTA_BUILD_PLAN.md).
The entries below start the forecaster work (v2), planned in [docs/plans/PLAN.md](docs/plans/PLAN.md).

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
- **Decision:** the forecaster plan lives in `docs/plans/PLAN.md`. `docs/plans/TORMENTA_BUILD_PLAN.md` gets a pointer line and is
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
- **Superseded by D-63** (2026-11-16): after the test was scored, the window was extended to 2026-06-30.
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
- **Addendum (D-61):** the raw probabilities lean high in quiet periods (training has more storm days than recent
  years). Warnings are unaffected, because the thresholds were chosen on those same raw probabilities.
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

### D-52 · Test period scored once (2020-01-01 → 2026-06-30) · 2026-11-13 · ✅
- **Decision:** `python -m src.forecast.test_eval` scored every model as it runs live (fitted ≤ 2019), plus NOAA,
  on 2,379 issue days with 325 storm days, including the May 2024 superstorm. The headline models were fixed
  and committed first (D-51). A marker file, `reports/forecast/test_scored.json`, blocks a second run without
  `--force`; a test checks this.
- **Run history (full disclosure):** the first attempt crashed **before producing any result**. The script
  forgot to fit the baselines, which the daily job refits on every run. The fix was one line, and the second
  attempt is the only scored run.
- **Result / consequence:**

  | Ap | RMSE day 1 | day 2 | day 3 | days 4–7 | mean skill vs 27-day avg (validation → test) |
  |---|---|---|---|---|---|
  | **HistGB** | **10.79** | 11.97 | 11.91 | **11.92–12.00** | 0.177 → **0.100** |
  | NOAA (days 1–3) | 10.89 | **11.73** | **11.90** | — | 0.091 → 0.134 |
  | ARIMAX | 10.96 | 12.12 | 12.15 | 12.16–12.17 | 0.046 → 0.069 |
  | ARIMA | 10.97 | 12.16 | 12.20 | 12.21–12.22 | −0.004 → 0.062 |
  | SARIMA | 11.11 | 12.37 | 12.43 | 12.46–12.49 | −0.198 → 0.025 |
  | Chronos | 11.83 | 12.56 | 12.66 | 12.64–12.65 | −0.039 → −0.015 |
  | 27-day average | 12.27 | 12.42 | 12.45 | 12.45–12.48 | 0 |

  - **HistGB is the best of our models at every lead day** and beats the 27-day average at every lead day.
  - **Against NOAA on days 1–3 it is level, not ahead:** better on day 1, NOAA better on day 2, tied on day 3.
    HistGB's mean skill over days 1–3 is about 0.128, NOAA's 0.134. The validation claim "beats NOAA on days
    1–3" does **not** hold on test; the report states the test result.
  - **D-23 confirmed:**
    - HistGB's skill fell from validation (quiet minimum) to test (active cycle 25).
    - The ARIMA family improved on test, because its pull toward the long-term mean (D-42) hurts in quiet years
      and helps in active ones.
  - **80% ranges: test coverage is 80–82% at every lead day** for HistGB and ARIMAX. They are well calibrated
    on fully unseen data.
  - **Storm warning:**

    | lead day | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
    |---|---|---|---|---|---|---|---|
    | Heidke skill | 0.30 | 0.22 | 0.21 | 0.21 | 0.21 | 0.21 | 0.20 |
    | storms caught | 54% | 39% | 40% | 43% | 42% | 43% | 29% |

    - About 7 in 10 warnings are false alarms.
    - It is the best storm signal on days 2–7: recurrence 0.16; every regression model about 0.0–0.03.
    - Persistence edges it on day 1 (0.32 vs 0.30).
  - **May 2024 case study** (`04_may2024_case_study.png`): no model forecast the superstorm's onset (Ap 271 on
    11 May). Storm risk was 8% the day before onset, then 84–87% for 11–13 May once it had begun. NOAA, which sees
    the CMEs in solar images, forecast the jump. This is the limit of forecasting from past values alone.
- Files: `reports/forecast/metrics/test_*.csv`, `reports/forecast/test_*forecasts.csv.gz`, and
  `reports/forecast/figures/01–04` (skill vs lead day, storm skill vs lead day, test coverage, May 2024).

### D-53 · Retrain only when performance drops: forecaster monitor and nowcaster health check · 2026-11-13 · ✅ (replaces the details of D-12)
- **Decision:**
  - **Forecaster** (`src/forecast/monitor.py`, weekly in `retrain.yml`): HistGB's skill against the 27-day
    average over the last **56** target days of live scores (lead days 1–3).
    - "Degraded" means below the 5th percentile of the same quantity on the test period (**−0.26**).
    - A retrain happens only after **two degraded checks in a row**. The candidate is trained up to the start
      of a 6-month holdout of the newest definitive data, and it replaces the incumbent only if its Ap RMSE there
      is ≤ 1.02 × the incumbent's.
    - State is kept in `forecasts/monitor.json`.
  - **Nowcaster** (`src/update.py`): retrains only if new data exists **and** its holdout skill against
    persistence fell more than 0.10 below its test skill (0.558). Otherwise the status is `healthy_no_retrain`.
- **Why:**
  - The teacher's rule.
  - Skill against a reference, not raw error, because raw error jumps in every storm.
  - **28 days was too noisy:** the 28-day skill was below 0 in 37% of test windows, even though the model is fine
    overall (56 days: 27%; 91 days: 23%). 56 days is the compromise between noise and reaction time.
- **Alternatives considered:** a 28-day window (from the plan); a raw-RMSE threshold; keeping the scheduled weekly
  retrain.
- **Result / consequence:**
  - On the test period the monitor would have called for a retrain in 3 episodes (mid-2020, Aug 2023, Feb 2024):
    13 of 331 weekly checks. In each case the gate still decides.
  - Live it reports "insufficient data" (120 scored pairs needed, about 40 issue days) until about January 2027.
  - The scorecard shows its test-period history.
  - Tests (`tests/test_monitor.py`): the window skill, insufficient data, a retrain only after two degraded
    checks, and a healthy nowcaster not being retrained.
  - **A bug caught by those tests:** the nowcaster's return dict let the health details overwrite
    `"healthy_no_retrain"` with `"healthy"`. Fixed.

### D-54 · "Try the forecaster": edit the inputs, or pick a past date · 2026-11-13 · ✅
- **Decision:** a new app tab with two modes.
  - **Edit:** the last 30 days of Ap, max Kp and F10.7, with presets (quiet week, storm now, storm 27 days ago).
    HistGB, ARIMAX, the storm classifier and the simple rules reforecast instantly, with ranges and storm risk.
  - **Past date:** any issue day from 2020. The app shows the **saved out-of-sample forecasts** (the one-time test
    run and the recent hindcast, `forecasts/past_forecasts.csv.gz`, 1.3 MB) against what happened.
- **Why:**
  - It is the teacher's requirement for live inputs.
  - Re-running models on dates inside their training years would look better than it should; the saved test
    forecasts are honest.
- **Result / consequence:**
  - Example: issued on 8 May 2024, the storm cards warned for 11 and 12 May (both real storm days) and missed the
    onset on 10 May.
  - "Storm now" raises day-1 storm risk from about 8% to 56%.
  - `recent.csv` now holds observed values since Oct 2019, including F10.7.
  - Heavy imports are loaded lazily, so the browser Space still runs (edit mode tells the visitor to use the
    Streamlit app instead).

### D-55 · Scorecard tab, Hugging Face forecaster publishing, Flask forecast page · 2026-11-13 · ✅
- **Decision:**
  - **Scorecard tab:** test headline numbers; a model comparison for test, validation or recent; the storm table
    per lead day; the four figures; model health.
  - **Hugging Face:** the forecaster's models and settings in the model repo, a model-card section with the test
    results, and statsmodels pins. The daily job publishes after each new issue, as a non-blocking step.
  - **Flask:** `/forecast` and `/api/forecast`.
- **Result / consequence:** the workflow test caught an unquoted YAML value containing ": " in the new publish
  step. It's the same mistake that broke the Monday job on 8 Nov, and it was fixed before pushing.

### D-56 · Repository cleanup, and action versions · 2026-11-13 · ✅
- **Decision:**
  - Removed 11 files in `reports/v2/` that were byte-identical to `reports/figures` and `reports/metrics`, and
    repointed `docs/report_notes.tex` to the identical copies.
  - Removed `models/tormenta_v20261030_0737.joblib` (superseded; only mentioned in saved notebook output).
  - Updated the workflows to `actions/checkout@v5` and `actions/setup-python@v6` (Node 24).
- **Kept on purpose:**
  - `models/tormenta_v20261028.joblib` and `tormenta_v20261029_1003.joblib`: notebooks 04 and 05 load them. They
    were removed briefly, found by checking the notebooks, and restored before committing.
  - The unique `reports/v2` files.
  - `reports.zip` and `docs/report/overleaf_upload.zip`: they appear to be the report and Overleaf exports, so
    deleting them is for the report authors to decide.
- **Result / consequence:** about 10 MB less in the working tree; git history keeps everything. The README now
  covers the forecaster, and `docs/report_notes.tex` has a forecaster section with viva points.

### D-57 · Chart hover pinned to the last observed day in the forecast area (bug fix) · 2026-11-15 · ✅
- **Problem** (reported by HRK): in the 7-day forecast chart (and the "Try the forecaster" chart, which uses the same
  code), hovering over the forecast days showed the last observed day's date, and it didn't change while moving
  across the forecast days.
- **Cause:** the hover from D-36 used two "nearest point" layers, one for past days and one for forecast days. Each
  layer's nearest-point search covers the whole chart, not just its own days. The past-days layer was on top, so in
  the forecast area its nearest point was always the last observed day.
- **Decision:** one invisible full-height column per day, one day wide, instead of a nearest-point search. Hovering
  anywhere in a column selects that day. The columns never overlap. Past columns list only the observed value and
  forecast columns only the models, so D-36's "no null" property is kept.
- **Process:** the cause and fix were proposed first and applied after approval, on the dedicated `fixes` branch.
- **Result / consequence:**
  - Checked on the chart definition: no nearest search; 30 past and 7 forecast day columns; no overlap; no empty
    tooltip values.
  - The rendered chart looks unchanged, and the app runs without errors in both modes.
  - Mouse movement can't be simulated here, so the final check is a hover on the deployed app after merging.

### D-58 · ARIMAX's first live rows were added late on 12 Nov (origin 11 Nov) · 2026-11-15 · ✅
- **Finding:** ARIMAX joined the live log after it passed its rule on 12 Nov (D-41). For origin 11 Nov, its rows
  were added by a later run that day (16:16 UTC), after the other five models had been issued (about 07:00 UTC). That
  is the "late addition on the same origin" that D-33 avoided for HistGB.
- **Decision:** leave the log as it is. It is append-only (D-07), and every row records its own `issued_at`, so the
  timing is visible. From origin 12 Nov on, all six models are issued together.
- **Consequence:** live comparisons of ARIMAX for origin 11 Nov should note its later issue time.

### D-59 · Tuning folds with a gap; features built on the full history (bug fixes) · 2026-11-16 · ✅
- **Problem 1 (tuning, introduced in the day-3 commit):** HistGB's `TimeSeriesSplit` had no gap. A row is an issue
  day D with a target on D+h (h ≤ 7), so the last training rows of each fold had targets inside the next
  validation fold. The CV scores were slightly optimistic. Validation and test were never affected.
- **Problem 2 (features, a side effect of D-19):** `training_rows()` cut the history at 1947-06-01 *before* the
  features were built, so 80 of 26,512 training days had empty lag or long-window features although GFZ data exists
  from 1932.
- **Decision:**
  - `gbm.cv_folds()` uses `gap = max lead (7)`.
  - `training_rows()` now prepends `FORECAST_HISTORY_DAYS` (130) days flagged `lead_in`. HistGB and the storm
    classifier use them for features only. `base.sample_rows()` drops them for every model that learns from the rows
    themselves (climatology, the ARIMA family), so D-19's common start date is kept.
  - Tests: no fold's training targets reach its validation fold; the first training day's features equal those
    built from the full history.
- **Process:** proposed in the audit notes, approved by HRK, done on the `fixes` branch; one retraining run.
- **Result:**
  - Tuning: every CV score rises by 0.01–0.06% (the removed optimism); **the same settings are chosen**, raw Ap target.
  - HistGB validation: mean Ap skill vs the 27-day average +0.177, **PASS**, unchanged. RMSE per lead day moves by
    at most ±0.006 (Ap) and ±0.004 (max Kp), in both directions.
  - Storm classifier: thresholds now 0.26 / 0.25 / 0.29 / 0.23 / 0.24 / 0.23 / 0.31 (were 0.21–0.29). The
    Heidke-vs-threshold curve is flat near its peak, so small probability changes move the best threshold.
    Validation Heidke skill is equal or higher at every lead day (day 1: 0.365 → 0.395); Brier unchanged.
  - Other models: identical validation results, as intended.
  - 80% ranges recalibrated; recent coverage unchanged (Ap 81–83%, max Kp 76–78%).
- **Not done:** the test period was scored once with the previous HistGB and classifier (D-52). It is not re-scored
  here; the app's past forecasts show the test run (previous version) followed by the recent hindcast (this
  version).

### D-60 · Measured: preliminary inputs vs revised inputs (docs/plans/PLAN.md §3) · 2026-11-16 · ✅
- **Question:** live forecasts read GFZ's newest, still preliminary values; the models trained on definitive ones.
  How much does that change a forecast?
- **Method:** `python -m src.forecast.checks skew`. The daily job commits the observations it used
  (`forecasts/recent.csv`), so git history holds each day's inputs as first published. For each live issue day,
  the production models forecast from those inputs and from the same days as GFZ publishes them now.
- **Result (5 issue days, 10–14 Nov):** one input value revised (a max Kp by ⅓). HistGB forecasts change by at most
  0.12 Ap and 0.04 max Kp; storm probability by at most 0.004; ARIMAX max Kp by at most 0.18. Negligible next to
  the models' errors (Ap RMSE about 9 on recent days).
- **Limit:** this covers the early revisions (nowcast → provisional) only. GFZ is definitive to 2026-06-30, so the
  final revision of the live period can be measured only when those days become definitive; the same command
  will then measure it.

### D-61 · Measured: storm probability calibration (prior shift, D-48) · 2026-11-16 · ✅
- **Question:** training has 22% storm days, recent years 8–14%. Do the raw probabilities lean high?
- **Method:** `python -m src.forecast.checks reliability`: probabilities grouped in bins and compared with the
  observed storm frequency, on 2008–2016 (fit ≤ 2007), validation 2017–2019 (fit ≤ 2016) and the recent hindcast
  (production model). The test period is not used.
- **Result:**
  - Validation is close to calibrated (mean probability 0.093 vs 8.3% storm days).
  - 2008–2016 and recent lean high: mean probability 0.138 vs 9.3%, and 0.165 vs 11.9%. In the 10–30% bins
    storms happen about two thirds as often as forecast (e.g. recent 10–20%: forecast 14%, observed 11%).
  - Above 40% the probabilities are about right.
- **Consequence:** warnings are unaffected (thresholds chosen on these same raw probabilities). The displayed
  "storm risk %" reads somewhat high on quiet stretches. A recalibration fitted on 2008–2016 is a separate
  proposal, pending approval.


### D-62 · Test period re-scored once for the D-59 models · 2026-11-16 · ✅
- **Why a second run (`test_eval --force`):** D-59 fixed two bugs and retrained HistGB and the storm classifier.
  The test score from D-52 describes the previous versions, which are no longer live.
- **Why it's still a fair test:** the fixes were proposed from a code audit and approved before any test number of
  the new models existed; tuning, the validation rule and the thresholds used only data up to 2019. Nothing in
  D-59 was chosen by looking at test results, and no choice will be made from this run.
- **Rule:** this run is reported as the test result of the current models, whatever it shows. The D-52 numbers
  stay in git history for comparison.
- **Result** (2020-01-01 → 2026-06-30, 2,379 issue days, 325 storm days):
  - HistGB: practically unchanged. Ap RMSE day 1 10.785 → 10.779 (NOAA 10.89), days 2–7 within ±0.01; max Kp
    within ±0.001. 80% range coverage 80–81% (Ap), 79–80% (max Kp). Every other model identical.
  - Storm classifier, Heidke skill by lead day 1–7: 0.341 / 0.195 / 0.204 / 0.205 / 0.215 / 0.202 / 0.188
    (D-52: 0.305 / 0.215 / 0.214 / 0.214 / 0.205 / 0.212 / 0.203). Day 1 improves (153 hits, 221 false alarms
    vs 174 and 329); the other days move by −0.02 to +0.01. Brier unchanged (0.099–0.111). The changes follow
    the new thresholds, not new information: as noted in D-59, the best threshold is poorly determined on a flat
    curve.

### D-63 · Live models refitted on every definitive day up to 2026-06-30 · 2026-11-16 · ✅
- **Why:** D-27 fixed the live fitting window at 1947–2019 so the test period stayed unseen. The test is now scored
  (D-62), so holding back 6.5 years of definitive data, the whole of solar cycle 25 so far, only costs the live
  forecasts. Refitting on all data once the test is done is the standard last step.
- **Decision:**
  - `config.PRODUCTION_END = 2026-06-30` (GFZ's last definitive day); `production_window()` fits up to it.
  - Refitted: HistGB, the storm classifier, ARIMAX and the baselines, with their selected settings unchanged.
    The storm thresholds and the 80% ranges stay as calibrated (out-of-sample errors from fits ≤ 2007 / ≤ 2016).
  - `test_eval` now fits its models afresh on ≤ 2019 instead of loading the live bundles, so the test stays
    reproducible.
  - The monitor's retrain needs its 6-month holdout to lie after the incumbent's training window. Until GFZ has
    6 months of definitive data after 2026-06-30, a due retrain is recorded as skipped instead of failing.
- **Rule, written before the refit:** keep the refit unless, on the recent hindcast (2026-07-01 onwards, unseen by
  both versions), its mean Ap skill vs the 27-day average over lead days 1–7 is ≤ 0. The ≤ 2019 models are
  reported beside it either way. This period is short (about 4.5 months), so it's a sanity check, not a contest.
- **Result** (`python -m src.forecast.refit`; recent hindcast 2026-07-01 → 2026-11-15, 144 issue days, both
  versions on the same days):
  - HistGB mean Ap skill vs the 27-day average: **+0.083** refitted vs +0.075 for the ≤ 2019 model → **rule passed,
    refit kept.** Ap RMSE lower at every lead day (day 1 8.94 → 8.89); max Kp skill +0.135 vs +0.136.
  - Storm classifier: mean Heidke skill 0.263 vs 0.219 (40 hits / 75 false alarms vs 34 / 74); Brier 0.0958 vs
    0.0961. Few storm days (16 per lead), so this is indicative only.
  - ARIMAX: practically unchanged (Ap skill +0.001 vs 0.000).
  - 80% ranges on the recent days: HistGB Ap 81–83%, max Kp 75–77%.
- **Scope of the scores:** the test result (D-62) belongs to the ≤ 2019 models. The refitted models can't be scored
  on 2020–2026 (they learned from it); their evidence is the recent hindcast and the live log.

### D-64 · Storm-risk % recalibrated (display only) · 2026-11-16 · ✅
- **Problem (D-61):** the classifier's raw probabilities lean high in quiet periods (recent: mean 16.5% vs 11.9%
  storm days), so the "storm risk %" in the app overstates the chance.
- **Decision:** per lead day, a logistic correction of the raw probability, sigmoid(a · logit(p) + b), fitted on
  2008–2016 probabilities of the model fitted ≤ 2007 (the same out-of-sample rows that chose the thresholds; never
  validation, test or recent days). The correction is increasing (a > 0 is checked), and each threshold is passed
  through it too, so **every warning stays exactly as before**; only the displayed chance changes. The raw
  probability is kept as `storm_prob_raw`. The test result (D-62) stays as scored, on raw probabilities.
- **Rule, written before fitting:** keep the correction only if the Brier score on validation 2017–2019 (model fitted
  ≤ 2016, correction from 2008–2016) is no worse than with raw probabilities. The recent hindcast and the
  reliability table are reported beside it.
- **Result: correction dropped.** Validation Brier 0.0658 corrected vs 0.0656 raw, so the rule fails. Fitted
  corrections lowered every lead day's chance (a 1.02–1.11, b −0.50 to −0.22).
  - For the record, on the recent days it would have helped: Brier 0.0938 vs 0.0958, mean chance 11.2% vs 16.6%
    against 11.6% storm days. The rule was fixed on validation, so that doesn't change the decision.
  - Reading: the lean depends on the period (none in the 2017–2019 solar minimum, clear in 2008–2016 and recently),
    so one fixed correction doesn't transfer reliably. The app keeps the raw chance; D-61's caveat stays.
  - The code path stays (`StormClassifier.calibrate`, `storm_prob_raw`) but is inactive: the bundle has no
    calibration, so every output equals the raw probability.

### D-65 · Dashboard redesign · 2026-11-17 · ✅
- **Why:** the old dashboard was Streamlit's default look with emoji labels; HRK asked for a rebuild that reads as
  designer-made, previewed as HTML before any code, then built and checked on localhost before merging.
- **Decision:**
  - Designed first on a canvas (palettes, then every screen), approved, then built in Streamlit (restyled, not
    replaced, so the Streamlit Cloud app and the in-browser Space keep working).
  - Themes: Carbon & Ice (dark, default) and Flight Manual (light), chosen by HRK; one primary colour for data and
    controls, one alert colour reserved for warnings and always paired with a text label.
  - Six pages linked through the URL (`?page=…&theme=…`): Overview, Forecast, Explore, Scorecard, Nowcast, Method.
  - Animated night-sky heroes: the Overview aurora follows the live Kp level; other pages use a solar flare, a real
    NASA EPIC Earth loop, a nebula, interplanetary dust and a NASA/JPL black-hole illustration. Real images are
    credited in the README with their licences.
  - Custom cursor and trailing ring, scrollbar and hover states; reduced-motion users get no animation; a phone
    layout below 720 px.
  - No logic changed: the pages call the same data loaders and models as before (moved to `app/tormenta_ui`).
- **Checks:** every offline page renders in both themes without an exception (`tests/test_dashboard.py`); the
  Explore edit mode and the Nowcast what-if were exercised headlessly; each page was screenshot at desktop width and
  the Overview at phone width.

### D-66 · Training start year: keep 1947 · 2026-11-18 · ❌ (shorter history rejected)
- **Question:** solar cycle 25 is quieter than the mid-century cycles (training 22% storm days, recent years 8–14%).
  Does a shorter, more recent training history fit the present better?
- **Method:** `python -m src.forecast.experiments.start_year`. Start years 1947, 1980, 1995 and 2010, all trained to 2022-12-31.
  Settings and storm thresholds chosen inside each variant's own years (5 time-ordered folds, 7-day gap), scored on
  2023-01-01 → last definitive day. No live file touched.
- **Result:**

  | Start | Train days | Ap skill 1–7 | Max Kp skill 1–7 | Storm Heidke day 1 | Heidke mean 1–7 |
  |---|---|---|---|---|---|
  | **1947** | 27,608 | **0.103** | **0.095** | **0.367** | **0.211** |
  | 1980 | 15,706 | 0.094 | 0.093 | 0.368 | 0.186 |
  | 1995 | 10,227 | 0.095 | 0.094 | 0.344 | 0.134 |
  | 2010 | 4,748 | 0.049 | 0.046 | 0.272 | 0.095 |

  Every shorter history is worse, and 2010 loses half the skill. Storms are rare, so the model needs every cycle's
  storms. The base-rate difference is already handled by the thresholds.
- **Decision:** no change; training keeps starting at 1947-06-01 (D-19).
- **Caveat:** the scoring window 2023 → is inside the test period, which D-62 had already scored. This run only
  confirmed the existing setting, so no test number was used to adopt anything. Later candidate changes are judged
  on 2011–2019 only (D-68).

### D-67 · CME catalogue features (NASA DONKI) · 2026-11-18 · ❌
- **Question:** coronal mass ejections cause the largest storms, 1–4 days after eruption. Do CME catalogue features
  add skill for lead days 1–3?
- **Data:** NASA DONKI through api.nasa.gov (`python -m src.ingest.fetch_donki`, key from `NASA_API_KEY`, never
  stored). Only information available at issue time is used: an entry counts from its `submissionTime`, and an
  arrival prediction from its model run's completion time. DONKI is kept in real time from April 2014 only, so
  the features are blank before then. Raw CME counts are excluded because logging practice changed after 2021.
- **Features:** fast CMEs (≥ 800 km/s) and the fastest speed in the last 3 days, Earth-facing wide CMEs, and
  WSA-ENLIL predicted arrivals (on the target day, within ±1 day, highest predicted Kp).
- **Result:**
  - First run (`cme_experiment.py`, trained ≤ 2022, scored 2023 →): Ap skill 0.103 → 0.108, storm Heidke day 1
    0.367 → 0.398, mean Heidke 1–7 0.211 → 0.180.
  - Yearly validation (D-68, 2015–2019): Ap skill +0.0005, max Kp +0.0006, but storm Heidke day 1
    0.369 → 0.312 and days 1–3 −0.0096. It meets the D-68 rule only by 0.0004 on the Heidke condition.
  - Added to the best solar-wind variant (D-68, `sw_rec_poisson_cme`): Heidke days 1–3 −0.023, **fails the rule**.
- **Decision:** not adopted. The gain is within noise, the two evaluations disagree on its sign for storms, and it
  would add a keyed external dependency to the daily job.
- **Caveat:** like D-66, the first run scored on 2023 →, inside the test period; it led to no adoption.
- **Kept:** `fetch_donki.py` and `cme_experiment.py` as the record. `data/raw/donki_cme/` stays untracked.

### D-68 · Yearly validation of forecaster changes; solar wind + 27-day echo + Poisson loss passes · 2026-11-19 · ⏳
- **Why a new harness:** D-66 and D-67 scored on 2023 →, which is inside the spent test period, and one
  validation block (2017–2019, solar minimum) is too short to judge small changes.
- **Method:** `python -m src.forecast.validate_yearly`. For each year 2011–2019: train on definitive days whose
  target is before 1 January of that year, then forecast the whole year. That gives nine years, 362 storm days and
  a full solar cycle. HistGB settings stay as live; only the tested change differs. Storm thresholds are chosen on
  2011–2014 and Heidke is scored on 2015–2019. The test period is never read (asserted in `run_block`).
- **Rule, fixed before any run:** keep a change only if (1) pooled skill vs the 27-day average improves (Ap, or max
  Kp for Kp-targeted changes), (2) it wins in at least 2/3 of the years (6 of 9; CME 4 of 5), and (3) storm Heidke
  days 1–3 does not drop by more than 0.01.
- **Result:**

  | Variant | Ap skill | Max Kp skill | Ap wins | Kp wins | Heidke 1–3 Δ | Rule |
  |---|---|---|---|---|---|---|
  | baseline (live) | 0.089 | 0.099 | — | — | — | — |
  | Poisson loss | 0.093 | 0.100 | 6/9 | 5/9 | 0 | pass |
  | log(Ap) target | 0.103 | 0.099 | 5/9 | 0/9 | 0 | fail |
  | storm classifier retuned | 0.089 | 0.099 | — | — | +0.007 | fail (no value gain) |
  | CME (D-67) | 0.089 | 0.100 | 5/5 | 4/5 | −0.010 | pass (barely) |
  | solar wind (day D, D−1) | 0.106 | 0.118 | 8/9 | 8/9 | −0.001 | pass |
  | solar wind + 27-day echo | 0.107 | 0.124 | 8/9 | 9/9 | +0.017 | pass |
  | **solar wind + echo + Poisson** | **0.112** | **0.124** | **9/9** | **9/9** | **+0.017** | **pass** |
  | the same + CME | 0.112 | 0.124 | 5/5 | 5/5 | −0.023 | fail |

  - Solar-wind features: daily means/extremes of speed, Bz, V·Bs, density, |B| and peak pressure for issue day D
    (plus speed and V·Bs of D−1, speed change), from OMNI hourly, 1998 onward (blank before).
  - The 27-day echo: speed (and By) one solar rotation before the target day, which captures recurring fast
    streams and sector structure.
  - The gain is spread over all lead days, not only day 1: Ap skill per lead day goes from 0.232 / 0.078 /
    0.066 / 0.062 / 0.061 / 0.062 / 0.059 to 0.264 / 0.099 / 0.086 / 0.083 / 0.087 / 0.083 / 0.083. This revises the
    expectation in D-05 ("helps only day 1"): the stream that is passing on day D tells the model how long the
    disturbance may last.
  - Weak years remain: 2011 and 2014 (solar maximum) are still below the 27-day average (−0.009, −0.035; baseline
    −0.058, −0.123).
- **Status:** the winner `sw_rec_poisson` is a candidate, not adopted. It was validated on OMNI, a corrected
  archive, while live forecasts would read NOAA's real-time feed (7 days of data). Adoption depends on D-69.
- **Not adopted:** log(Ap), the storm classifier retune, and CME (D-67).
- **Files:** `reports/forecast/experiments/yearly/summary.csv` and `ap_skill_by_year.csv` are committed. The
  per-variant `forecasts.csv` / `storm_probs.csv` (about 4 MB each) are regenerated by the command and not
  committed.

### D-69 · Solar-wind candidate with live-like inputs: stress test · 2026-11-19 · ⏳
- **Question:** `sw_rec_poisson` (D-68) learned from OMNI. Live, it would read NOAA's real-time feed: 7 days only,
  with gaps, different instruments and no reprocessing. Does the gain survive?
- **Why synthetic:** the real check (archived DSCOVR real-time data for 2017–2019 vs OMNI) could not be run:
  NOAA's servers timed out, and no netCDF reader is installed. It is listed in [TODO.md](TODO.md).
- **Method:** `python -m src.forecast.experiments.sw_live_stress`. The models are fitted as in D-68 on clean OMNI, and only the
  forecast inputs are degraded. Same years, rule and scoring as D-68. Degradation sizes are assumptions, chosen
  on the pessimistic side:
  - `gaps`: 10% of hours lost; in fast or dense hours (> 600 km/s or > 15 cm⁻³) 30% of plasma values lost; 3% of
    days lost entirely.
  - `noise`: hourly speed × N(1.02, 0.03), density and pressure × 1.25, Bz and By + N(0, 1 nT), |B| + N(0, 0.5 nT).
  - `no_archive`: the 27-day echo blank (the live feed holds 7 days).
  - `worst`: all three together.
  - `no_sw`: every solar-wind input blank (feed down).
- **Result:**

  | Scenario | Ap skill | Ap wins | Max Kp skill | Kp wins | Heidke d1 | Heidke 1–3 | D-68 rule |
  |---|---|---|---|---|---|---|---|
  | live model (baseline) | 0.089 | — | 0.099 | — | 0.369 | 0.294 | — |
  | clean (= D-68) | 0.112 | 9/9 | 0.124 | 9/9 | 0.390 | 0.311 | pass |
  | gaps | 0.111 | 8/9 | 0.124 | 9/9 | 0.395 | 0.312 | pass |
  | noise | 0.108 | 8/9 | 0.122 | 9/9 | 0.348 | 0.274 | **fail** (Heidke −0.020) |
  | no_archive | 0.102 | 6/9 | 0.106 | 6/9 | 0.370 | 0.297 | pass |
  | worst | 0.098 | 6/9 | 0.102 | 6/9 | 0.393 | 0.306 | pass |
  | no_sw (feed down) | **0.075** | 0/9 | **0.075** | 0/9 | 0.365 | 0.281 | **fail** |

- **Reading:**
  - Gaps cost almost nothing.
  - The value forecasts keep most of their gain under noise and bias. Storm warnings do not: under `noise`, Heidke
    days 1–3 falls below the live model. Its `worst` result is fine, so the warnings react to the input bias in
    an unstable way. The thresholds are sensitive to a shift in the input scale.
  - Without the 27-day archive, about half the gain is lost: still 6/9 years, barely passing.
  - **With the feed down, the candidate is worse than the live model** (0.075 vs 0.089). A model that learned to
    lean on solar wind does poorly without it.
- **Consequences, if the candidate is adopted:**
  1. Archive the daily solar-wind summary in the daily job, so the 27-day echo is available after 27 days.
  2. Keep the current model as the fallback, and use it whenever the day's solar wind is missing.
  3. Run the candidate in shadow mode (logged, not shown as the main forecast) and compare it with the live
     model on the same days. Do the real DSCOVR-vs-OMNI check (TODO.md). If real-time inputs are biased against
     OMNI, rescale them before forecasting.
- **Status:** candidate, not adopted. Shadow run approved and built (2026-11-19):
  - `src/ingest/sw_archive.py`: the daily job keeps NOAA's real-time solar wind hour by hour in
    `forecasts/solar_wind_hourly.csv`. Real-time data only, never overwritten with OMNI, so the archive later gives
    the real-time vs OMNI comparison on the same hours. A later fetch only fills gaps.
  - `src/forecast/sw_shadow.py`: `sw_rec_poisson` fitted on the live window (definitive days to `PRODUCTION_END`),
    OMNI solar wind for training, saved as `models/forecast/sw_shadow.joblib`. Features checked identical to the
    validated variant. Each run appends to `forecasts/shadow_log.csv`: the candidate's values and storm
    probability, the live HistGB values, and `sw_status` (`full`, `no_echo` while the archive is shorter than 27
    days, `no_sw`). With `no_sw` the served value is the live HistGB forecast (fallback). A failure in the shadow
    step never blocks the live forecast.
  - Adoption still needs: several weeks of shadow scores, and the real-time vs OMNI check with rescaling if biased.

### D-70 · Solar imagery (coronal holes) as a forecaster input: rules before any data · 2026-11-20 · ⏳
- **Idea:** coronal holes release fast solar wind that reaches Earth about 2–4 days after a hole crosses the
  Sun's central meridian. Days 2–7 are the forecaster's weakest; the solar-wind features (D-68) describe only the
  wind arriving now. Daily coronal-hole measurements from extreme-ultraviolet images could add lead time.
  Not expected: much help with CME storms (D-67).
- **Data:** SDO/AIA 193 Å, one image per day, May 2010 onward (JSOC synoptic archive or SDOML). Simple measured
  features, no deep network: coronal-hole area near the central meridian, mean darkness, latitude, 1–3 day change.
- **Isolation:** code in `src/forecast/imagery/`, images in `data/raw/imagery/` (not committed), results in
  `reports/forecast/experiments/imagery/`. Nothing in `models/`, `src/issue.py`, `forecasts/` or the daily job
  changes. Live-file fingerprints are checked before and after each step.
- **Test period:** not used. Validation on 2011–2019 only, with the D-68 yearly harness; the 2020 → test runs once,
  after the model is locked.
- **Rule, fixed before any run.** The variant is the current candidate (`sw_rec_poisson`, D-68) plus the imagery
  features, compared with that candidate on the same days. Judged on **2013–2019** (7 years), because images start
  in May 2010 and earlier years would rest on under 2.5 years of image history. Keep only if all hold:
  1. pooled Ap skill vs the 27-day average improves;
  2. Ap skill on lead days 2–4 (pooled) improves, since that is the purpose;
  3. it wins in at least 5 of the 7 years (Ap);
  4. storm Heidke days 1–3 (thresholds tuned on 2011–2014, scored 2015–2019) drops by no more than 0.01.
- **Stop early** if the sanity check fails: on 2011–2019, coronal-hole area near the central meridian shows no
  relation to solar-wind speed or Ap 2–4 days later.
- **Live use, only if it passes:** compare the archive images with the real-time source (GOES SUVI 195 Å or SDO
  near-real-time), as D-69 did for solar wind, then shadow mode.
- **Download trial (2026-11-20):** June 2015 from the JSOC AIA synoptic archive
  (`jsoc1.stanford.edu/data/aia/synoptic/YYYY/MM/DD/H0000/`): 30 of 30 daily 193 Å files at 00:00 UTC, 1024×1024,
  quality flag 0, 37 MB in 56 s (4 parallel). No account needed. Reading them needs `astropy`, installed in the local
  environment only (`requirements.txt` unchanged, numpy/scikit-learn/pandas untouched). A rough cut (pixels below
  0.35 × the disk median) finds 1–8 % of the disk dark and shows the coronal hole crossing the centre on 10–13 June;
  it also catches filaments, so step 3 needs a size and shape filter. The header's `R_SUN` is in 4096-px units;
  the radius for these images is `RSUN_OBS / CDELT1` (about 394 px).
- **Full download estimate:** about 6,000 days (May 2010 → now), about 7.4 GB, about 3 hours at the trial speed.
- **One-year check, 2016 (the stop-early test):** 357 of 366 days usable (no 00:00 image on 1 June and 3–10 August).
  Low-latitude coronal-hole area in the Earth-facing strip vs what arrives later: wind speed +0.51 / +0.68 / +0.66
  at 2 / 3 / 4 days, log Ap +0.49 / +0.50 / +0.33. Added value, by blocked cross-validation over the four quarters
  of 2016, with a 5-input linear model that already has today's and yesterday's Ap, today's wind speed and the
  27-day echo of Ap and wind speed: log-Ap error 2 / 3 / 4 days ahead falls by 8.6 / 8.5 / 7.3 %, better in
  4 / 3 / 3 of 4 quarters. **Passes the stop-early test.** Not a model result: the real candidate is far stronger
  than this 5-input model, and 2016 (declining phase) favours coronal holes, so the D-70 rule decides.
- **Full test (2026-11-21):** images for 13 May 2010 – 31 Dec 2019 (3,489 files; 31 days have no 00:00 image;
  22 images skipped for a non-zero quality flag), daily features in
  `reports/forecast/experiments/imagery/ch_features.csv` (`python -m src.forecast.imagery`; 3,467 days; identical to
  the one-year check on sampled days). Variant `sw_rec_poisson_imagery`: the candidate plus, for issue day D,
  low-latitude Earth-facing area (D, D−1, D−2, change since D−1), incoming area, disk area and darkness, all from
  images at or before 00:00 UTC on D.

  | Check (2013–2019) | Candidate | + coronal holes | |
  |---|---|---|---|
  | 1. Pooled Ap skill | 0.131 | **0.160** | pass |
  | 2. Ap skill, lead days 2–4 | 0.110 | **0.155** | pass |
  | 3. Years better | — | **7 of 7** | pass |
  | 4. Storm Heidke days 1–3 (2015–2019) | 0.310 | **0.364** | pass (no drop) |

  - By lead day (Ap skill): 0.267 / 0.114 / 0.109 / 0.108 / 0.110 / 0.106 / 0.106 → 0.284 / 0.158 / 0.157 /
    0.149 / 0.146 / 0.116 / 0.111. The gain is largest on days 2–5, the travel time of fast wind from a coronal hole.
  - 2014 (solar maximum) moves from −0.035 to +0.029.
- **Decision: passes the rule. Candidate, not adopted.**
- **Leakage robustness (2026-11-21), two runs fixed before running:** a row for issue day D was checked to use the
  image file dated D. Then:

  | Run (2013–2019) | Pooled Ap skill | Days 2–4 | Years better |
  |---|---|---|---|
  | candidate, no images | 0.131 | 0.110 | — |
  | + coronal holes | 0.160 | 0.155 | 7 / 7 |
  | + previous day's image | 0.154 | 0.151 | 7 / 7 |
  | + images assigned to random days (placebo) | 0.137 | 0.116 | 4 / 7 (fails) |

  The gain survives a one-day delay (coronal holes change slowly) and mostly vanishes with shuffled dates, so it
  comes from the real images on their real dates. The placebo's small residue (+0.005) comes from images existing
  only from May 2010, which marks the era. **Passed.**
- **Live source (2026-11-21):** the archive (`jsoc1.stanford.edu/data/aia/synoptic/`) lags about 10 days, too
  late for a daily forecast. JSOC's near-real-time folder (`…/synoptic/nrt/YYYY/MM/DD/H0000/`, from 2023) has the
  same 1024×1024 level-1.5 FITS at 00:00 UTC the same day. Its quality word carries a near-real-time marker
  (bit 30), which the feature code now accepts (`imagery.usable`); all other quality bits still exclude an image.
- **Live-image check (2026-11-21):** 30 days (11 Oct – 9 Nov 2026, live period, not test) downloaded from both
  sources. Coronal-hole features agree to within a few hundredths of a percent (low-latitude Earth-facing area:
  mean 6.23 vs 6.22 %, typical difference 0.07, correlation 1.000; every feature correlation 1.000). **Passed:** live
  inputs match training inputs; no rescaling needed.
- **Next:** shadow mode (daily fetch of the near-real-time image, features, logging next to the live model, with
  fallbacks); the final test runs once after the lock.

### D-71 · NOAA's storm-forecast skill, measured on validation years · 2026-11-20 · ⏳
- **Why:** before any storm-warning work (ROADMAP §3), know what "good" looks like: how often NOAA's official
  forecast catches a storm day, on the same days and with the same storm definition as ours.
- **Data:** NOAA's daily RSGA reports, section VI "Geomagnetic Activity Probabilities": the chance of a minor storm
  and of a major-severe storm, middle latitudes, for 1, 2 and 3 days ahead. NOAA's storm chance = minor + major.
  Raw yearly archives from the SWPC FTP warehouse, kept in `data/raw/noaa_rsga_raw/` (not committed).
- **Days:** 2017–2019 only (NOAA's archive starts in 2017; 2020 onward is the closed test period).
- **Ours:** the storm probabilities already produced by the yearly validation (D-68) for those days, for the live
  model (`baseline`) and the candidate (`sw_rec_poisson`). Nothing is refitted.
- **Storm day:** GFZ daily max Kp ≥ 4.5 (Kp 5−), our definition. NOAA's categories are mid-latitude K indices, so
  the match is close but not exact; stated with the result.
- **Scores, fixed before looking:** Brier score and its skill against climatology (needs no threshold); storm days
  caught, false alarms and Heidke skill at each forecaster's own best threshold (the same procedure for all three,
  so equally optimistic); per lead day 1–3.
- **Isolation:** a script in `src/forecast/experiments/noaa_storm.py`, results in `reports/forecast/experiments/noaa_storm/`;
  nothing live changes.
- **Result** (`python -m src.forecast.experiments.noaa_storm`; 1,090 days, 91 storm days; all reports had the probabilities):

  | Lead | Forecaster | Brier skill | Caught | False alarms | Detection | False-alarm ratio | Heidke |
  |---|---|---|---|---|---|---|---|
  | 1 | NOAA | **0.221** | 33 | 23 | 36 % | **41 %** | **0.412** |
  | 1 | live model | 0.205 | 41 | 58 | 45 % | 59 % | 0.377 |
  | 1 | solar-wind candidate | 0.215 | 43 | 58 | **47 %** | 57 % | 0.395 |
  | 2 | NOAA | **0.185** | 30 | 24 | 33 % | **44 %** | **0.375** |
  | 2 | live model | 0.140 | 36 | 64 | 40 % | 64 % | 0.317 |
  | 2 | solar-wind candidate | 0.154 | 29 | 32 | 32 % | 53 % | 0.337 |
  | 3 | NOAA | 0.151 | 34 | 54 | 37 % | 61 % | 0.324 |
  | 3 | live model | 0.146 | 29 | 41 | 32 % | 59 % | 0.310 |
  | 3 | solar-wind candidate | **0.167** | 29 | 31 | 32 % | **52 %** | **0.340** |

  - Day 1: NOAA slightly ahead (Heidke 0.412 vs 0.395); ours catch more storm days but raise many more false alarms.
  - Day 2: NOAA clearly ahead (0.375 vs 0.337). This is the gap to close.
  - Day 3: the solar-wind candidate is ahead of NOAA (0.340 vs 0.324, Brier skill 0.167 vs 0.151).
  - Caveats: 2017–2019 is solar minimum (few CME storms, where NOAA's solar imagery matters most); 91 storm days,
    so differences of a few hundredths are within noise; best thresholds are optimistic for all three alike;
    NOAA's categories are mid-latitude K, ours planetary Kp.
- **Status:** measured. Target for ROADMAP §3: NOAA's day-1 and day-2 Heidke (0.41, 0.38) on these days.

### D-72 · Re-issue today and tomorrow every 3 hours: rules before any run · 2026-11-20 · ⏳
- **Idea:** the forecast is issued once, just after midnight UTC, and does not change during the day. At 03, 06,
  09, 12, 15, 18 and 21 UTC, update **today** (lead 0, a new product) and **tomorrow** from what has happened so far
  today. Days 2–7 stay once a day.
- **Inputs at update k (k = 1 … 7 blocks of today ended):** the live daily features as of yesterday (unchanged);
  today's ended Kp blocks (count k, highest Kp so far, Ap so far from the blocks' ap, last block, last-block change);
  today's solar wind up to the update time (OMNI hourly, 1998 onward, blank before: mean speed, most southward Bz,
  mean V·Bs, and the same for the last 3 hours). A block counts only once it has ended.
- **Not used:** the nowcaster's output (trained on data that includes 2011–2019, so it would leak); the solar wind
  it reads is used directly.
- **Model, fixed in advance:** one set of models per update time: HistGB regressors for Ap and max Kp (live
  settings, `histgb_params.json`) and a storm classifier (`storm.PARAMS`), for today and for tomorrow. No variant
  is chosen by its results.
- **Validation:** the D-68 yearly harness, 2011–2019: for each year, train on target days before 1 January of that
  year, forecast the year. The test period is not read.
- **Yardsticks:** the midnight forecast (the live model, D-68 `baseline`: lead 1 for today, lead 2 for tomorrow,
  issued the evening before); and a simple rule for today: max Kp = the higher of "max so far" and the midnight
  forecast; Ap = the blocks so far plus the midnight forecast for the blocks left.
- **Rule, fixed before any run. Keep only if all hold:**
  1. Tomorrow's storm warning at the 12 UTC update beats the midnight forecast: higher Heidke on 2015–2019, each
     forecaster's threshold tuned on 2011–2014.
  2. Tomorrow's false-alarm ratio on 2015–2019 at the 12 UTC update is not higher than the midnight forecast's.
  3. Today's max-Kp error (RMSE, 2011–2019 pooled) is lower than the simple rule's at the 06, 12 and 18 UTC
     updates.
  4. The 12 UTC update wins in at least 6 of the 9 years on tomorrow's storm Brier score (vs midnight) and on
     today's max-Kp error (vs the simple rule).
- **Isolation:** `src/forecast/experiments/intraday.py`, results in `reports/forecast/experiments/intraday/`; nothing live
  changes; fingerprints before and after.
- **Result** (`python -m src.forecast.experiments.intraday`; leakage tests `tests/test_intraday.py`, 17 pass):

  | Update | Today max-Kp error: model / simple rule / midnight | Today storm Heidke: model / midnight | Tomorrow storm Heidke: model / midnight | Tomorrow false-alarm ratio: model / midnight |
  |---|---|---|---|---|
  | 06 UTC | 0.82 / 1.00 / 1.12 | 0.60 / 0.37 | 0.27 / 0.27 | 0.69 / 0.68 |
  | 12 UTC | 0.69 / 0.94 / 1.12 | 0.77 / 0.37 | 0.31 / 0.27 | 0.63 / 0.68 |
  | 18 UTC | 0.49 / 0.87 / 1.12 | 0.86 / 0.37 | 0.31 / 0.27 | 0.58 / 0.68 |
  | 21 UTC | 0.33 / 0.82 / 1.12 | 0.94 / 0.37 | 0.34 / 0.27 | 0.57 / 0.68 |

  - Checks 1–3 pass: tomorrow's Heidke at 12 UTC 0.306 vs 0.272; false-alarm ratio 0.63 vs 0.68; today's max-Kp
    error below the simple rule at every update (0.82 / 0.69 / 0.49 vs 1.00 / 0.94 / 0.87).
  - **Check 4 fails:** at 12 UTC, today's max-Kp error beats the simple rule in 9 of 9 years, but tomorrow's storm
    Brier score beats the midnight forecast in only 5 of 9 (needed 6). Two of the losses are near-ties (2016 by
    0.00001, 2018 by 0.00017); counted as losses, as the rule states.
- **Decision: fails the rule; not adopted.** The "today" part is a large, consistent gain; the "tomorrow" part
  improves warnings on pooled scores but not consistently by year. Adopting "today" alone would be a rule chosen
  after seeing these results, so it is not done on this evidence. If wanted, write a new rule for a today-only
  product and judge it on data not yet seen (a live shadow run), not on 2011–2019 again.

### D-73 · Storm start vs continuation: how yesterday ended, as inputs · rules before any run · 2026-11-20 · ⏳
- **Why:** against NOAA (D-71), our storm warnings lose mainly on false alarms. A storm already under way at the
  end of the issue day is the easy case; a new storm is the hard one. The daily features describe whole days, not
  how the issue day ended.
- **One variant, fixed in advance (no others tried):** the current candidate (`sw_rec_poisson`, D-68) plus five
  inputs from the issue day's 3-hour Kp blocks, all known when the forecast is issued: the last block (21–24 UTC),
  the highest of the last four blocks, the number of blocks at Kp ≥ 4.5, storm days in a row ending on the issue
  day, and the change over the last four blocks (last minus first). Used by the value models and the storm
  classifier, all lead days. Same settings otherwise.
- **Validation:** the D-68 yearly harness, 2011–2019; the test period is not read. Compared with `sw_rec_poisson`
  on the same days.
- **Rule, fixed before any run. Keep only if all hold:**
  1. Storm Heidke, lead days 1–3 pooled (thresholds tuned on 2011–2014, scored on 2015–2019), is higher.
  2. The false-alarm ratio on the same days and thresholds is not higher.
  3. Storm Brier score, lead days 1–3, is lower in at least 6 of the 9 years.
  4. Pooled Ap skill vs the 27-day average drops by no more than 0.005 (the values must not get worse).
- **Isolation:** a variant in `src/forecast/validate_yearly.py`, results in
  `reports/forecast/experiments/yearly/sw_rec_poisson_progress/`; nothing live changes; fingerprints before and
  after.
- **Result** (`python -m src.forecast.validate_yearly sw_rec_poisson_progress`; leakage tests
  `tests/test_progress_features.py`, 3 pass):

  | Check | Candidate | + how the day ended | |
  |---|---|---|---|
  | 1. Storm Heidke, days 1–3 (2015–2019) | 0.310 | 0.317 | pass |
  | 2. False-alarm ratio, same days | 0.561 | **0.582** | **fail** |
  | 3. Storm Brier, days 1–3, years better | — | 7 of 9 | pass |
  | 4. Pooled Ap skill | 0.112 | 0.122 | pass |

  The new inputs raise detection (0.34 → 0.38) at a lower tuned threshold (0.26 vs 0.29), so warnings become more
  frequent and the false-alarm ratio rises: the opposite of the aim.
- **Decision: fails the rule (check 2); not adopted.** Not used: the Ap-skill gain (+0.010) is a finding the rule
  was not written for; adopting the variant for it would choose the reason after seeing the result. If wanted, it
  needs its own rule and data not yet seen (the final test or a shadow run).

### D-74 · Flare, radio and proton warning signs as inputs: rules before any run · 2026-11-20 · ⏳
- **Idea:** storms mostly come from CMEs, which leave no trace in past Kp or in the solar wind until they arrive.
  The Sun usually signals an eruption: a large X-ray flare, its position (near the disk centre it faces Earth),
  radio sweeps of type II/IV, and a proton shower. NOAA lists these daily since 1996, much longer than DONKI
  (2014, D-67), so the model sees far more storms to learn from.
- **Data:** SWPC edited event reports (`YYYY_events.tar.gz`) and daily particle data (`YYYY_DPD.txt`), 1996–2019,
  from the FTP warehouse, kept in `data/raw/noaa_events/` (not committed). 2020 onward is not downloaded.
- **Inputs for issue day D (events that began on D or the two days before; all before the forecast is issued):**
  largest X-ray flare (log peak flux); largest X-ray flare from a region whose optical flare position is within 30°
  of the disk centre; number of type II and of type IV radio sweeps; largest daily >10 MeV proton fluence (log).
  One variant, fixed in advance, added to the candidate (`sw_rec_poisson`, D-68); all lead days.
- **Validation:** the D-68 yearly harness, 2011–2019; the test period is not read. Compared with `sw_rec_poisson`.
- **Rule, fixed before any run. Keep only if all hold:**
  1. Storm Heidke, lead days 1–3 pooled (thresholds tuned on 2011–2014, scored on 2015–2019), is higher.
  2. The false-alarm ratio on the same days and thresholds is not higher.
  3. Storm Brier score, lead days 1–3, is lower in at least 6 of the 9 years.
  4. Pooled Ap skill vs the 27-day average drops by no more than 0.005.
- **Live use, only if it passes:** the archive files are written days after the day, while the live feed
  (`json/edited_events.json`) updates every few minutes; before adoption, log the live feed for some weeks and
  check that events appear in time (the D-67 lesson), then shadow mode.
- **Isolation:** `src/ingest/fetch_events.py`, a variant in `src/forecast/validate_yearly.py`, results in
  `reports/forecast/experiments/yearly/sw_rec_poisson_events/`; nothing live changes; fingerprints before and after.
- **Data, as downloaded:** 48 files, no failures. Event reports from 31 Jul 1996 (earlier 1996 days are not in the
  archive), 8,525 days; particle data for every year (two date layouts, both parsed; the largest >10 MeV fluence
  is 15 Jul 2000, the Bastille Day event, as expected). Parsing and leakage tests: `tests/test_events_features.py`.
- **Result** (`python -m src.forecast.validate_yearly sw_rec_poisson_events`):

  | Check | Candidate | + warning signs | |
  |---|---|---|---|
  | 1. Storm Heidke, days 1–3 (2015–2019) | 0.310 | 0.308 | **fail** |
  | 2. False-alarm ratio, same days | 0.561 | 0.584 | **fail** |
  | 3. Storm Brier, days 1–3, years better | — | 6 of 9 | pass |
  | 4. Pooled Ap skill | 0.112 | 0.118 | pass |

  Detection rises (0.34 → 0.36) but so do false alarms; warning skill does not improve.
- **Decision: fails the rule (checks 1 and 2); not adopted.** Noted, not used: storm skill is scored on
  2015–2019, the quiet end of the solar cycle, where few CME storms occur and flare signs matter least. A retry
  would need a rule written for active years before any run, judged on data not yet seen.

### D-75 · Report comparisons: Holt-Winters, LSTM, GRU on the yearly harness · 2026-11-20 · ✅
- **Purpose:** baselines for the report and viva (classical exponential smoothing and recurrent neural networks),
  scored exactly like HistGB. **Comparison only: none of these is a candidate, whatever the result.**
- **Same days and yardstick:** the D-68 harness rows (issue days through 2011–2019, lead days 1–7) and the same
  reference (the 27-day average); results line up with `baseline` and `sw_rec_poisson`.
- **Holt-Winters:** additive level + 27-day season (one solar rotation), one per target (daily Ap, max Kp).
  Smoothing parameters fitted on the 10 years before each validation year (one-step error); the recursion then
  rolls forward day by day, so a forecast issued on D uses observations up to D only.
- **LSTM and GRU:** one recurrent layer (64 units) reading the 81 days up to the issue day (Ap, max Kp, F10.7,
  season), predicting Ap and max Kp for lead days 1–7 together. For each validation year: trained on issue days
  whose targets are all before 1 January of that year, from 1947; early stopping on the last two years of that
  training span (time-ordered, with a 7-day gap); fixed scaling constants (nothing learned from the year forecast).
- **Leakage guards:** the test period is not read (asserted); tests check that a forecast for D is unchanged when
  data after D changes.
- **Isolation:** `src/forecast/experiments/report_models.py`; results in `reports/forecast/experiments/yearly/{holt_winters,
  lstm,gru}/`; no file in `models/`, `forecasts/` or the daily job changes; fingerprints before and after.
- **Result** (`python -m src.forecast.experiments.report_models hw lstm gru`; leakage tests `tests/test_report_models.py`,
  4 pass; table in `reports/forecast/experiments/report_models/summary.csv`):

  | Model | Ap skill | Ap RMSE d1 / d7 | Years above the 27-day average (Ap) | Max-Kp skill | Max-Kp RMSE d1 |
  |---|---|---|---|---|---|
  | HistGB + solar wind (candidate) | **0.112** | **7.42 / 8.38** | 7 / 9 | **0.124** | **1.08** |
  | HistGB (live model) | 0.089 | 7.58 / 8.49 | 6 / 9 | 0.099 | 1.12 |
  | GRU | 0.051 | 7.75 / 8.62 | 8 / 9 | 0.049 | 1.16 |
  | LSTM | 0.029 | 7.83 / 8.71 | 6 / 9 | 0.031 | 1.18 |
  | Holt-Winters | −0.108 | 8.69 / 9.24 | 1 / 9 | −0.032 | 1.30 |

  - Gradient boosting with hand-built features beats both recurrent networks clearly; the GRU beats the LSTM.
  - Holt-Winters is worse than the 27-day average: it follows day-to-day noise.
- **Status:** done; comparison only, nothing adopted.

### D-76 · Model locked: HistGB + solar wind + 27-day echo + coronal holes · test protocol fixed before any test data · 2026-11-21 · 🔒
- **Locked model ("HistGB-SW-CH"):** the D-68 yearly-harness variant `sw_rec_poisson_imagery`, exactly as validated:
  - inputs: the live HistGB features (D-31), daily solar wind of the issue day and the day before plus the 27-day
    echo of speed and By (D-68), and the coronal-hole features from the 00:00 UTC AIA 193 Å image (D-70);
  - 14 HistGB regressors with Poisson loss and the live settings in `histgb_params.json` (unchanged; no retuning);
  - the storm classifier with `storm.PARAMS` (unchanged) on the same inputs.
- **Live fallbacks:** no usable image in the last 2 days → the solar-wind model (`sw_rec_poisson`); no solar wind
  on the issue day → the live HistGB (D-69). Each logged row states which model served it.
- **Test protocol, fixed now and run once:**
  1. Fit on definitive days 1947-06-01 → 2019-12-31 (as the live models were fitted for D-52/D-62).
  2. Forecast every issue day from 2019-12-31 so that targets cover 2020-01-01 → 2026-06-30 (GFZ's last definitive
     day), lead days 1–7. Inputs: GFZ, OMNI hourly solar wind, AIA 193 Å images from the JSOC archive.
  3. Storm warning lines per lead day: the thresholds that maximise Heidke on the locked model's out-of-sample
     yearly-harness probabilities for 2011–2019 (no test data).
  4. Scores: Ap and max-Kp RMSE per lead day; skill vs the 27-day average (days 1–7); storm detection, false-alarm
     ratio and Heidke per lead day; the same for the live HistGB fitted to 2019 (D-62) and NOAA (Ap days 1–3, RSGA).
  5. Significance: Diebold–Mariano test on daily squared Ap errors (Newey–West variance, lag h−1) for the locked
     model vs NOAA (days 1–3) and vs the live HistGB (days 1–7), and a 30-day block bootstrap interval for the skill
     difference.
  6. Data gaps are reported, never filled from the future: if OMNI cannot be refreshed past 2026-01-10, the test is
     reported on 2020-01-01 → 2026-01-10 with full inputs, and 2026-01-11 → 06-30 separately with solar wind blank.
  7. A marker file blocks a second run; the result is recorded whatever it shows.
- **Adoption rule, fixed now:** the locked model replaces the live HistGB only if, on the test, (a) its pooled Ap
  skill (days 1–7) and day-1 Ap RMSE are better than the live HistGB's on the same days, (b) storm Heidke days 1–3
  is not lower by more than 0.01, and (c) a shadow run of at least 3 weeks shows no failure of the fallbacks.
- **Then:** refit on definitive days to `PRODUCTION_END` (images and solar wind included) for live use.
- **Why lock now:** the candidate passed its rule (D-68, D-70), the leakage robustness runs and the live-image
  check; further experiments on the same validation years would add selection risk.

### D-77 · One-time test of the locked model: adoption rules (a) and (b) pass; level with NOAA · 2026-11-21 · ✅
- **Run:** `python -m src.forecast.test_locked`, once, exactly as fixed in D-76 (fit ≤ 2019-12-31, targets
  2020-01-01 → 2026-06-30, 2,373 days, 325 storm days). Inputs: GFZ, OMNI hourly solar wind (complete for the whole
  period after the SPDF refresh), AIA 193 Å features for 2,360 of 2,373 days (6 days with no 00:00 image in the
  archive, 7 with a quality flag; those rows have blank image features, which HistGB routes as missing).
  Results in `reports/forecast/test_locked/`; the marker `test_scored.json` blocks a second run.
- **Daily Ap RMSE and Diebold–Mariano vs the live HistGB (D-62 test forecasts, same days):**

  | Lead | Locked | Live HistGB | NOAA | 27-day mean | DM vs HistGB (stat, p) |
  |---|---|---|---|---|---|
  | 1 | **10.67** | 10.78 | 10.89 | 12.27 | −1.69, 0.091 |
  | 2 | 11.80 | 11.98 | **11.73** | 12.42 | −2.77, 0.006 |
  | 3 | **11.73** | 11.91 | 11.90 | 12.45 | −2.25, 0.025 |
  | 4 | **11.69** | 11.91 | – | 12.45 | −2.98, 0.003 |
  | 5 | **11.72** | 11.93 | – | 12.45 | −3.78, < 0.001 |
  | 6 | **11.88** | 11.96 | – | 12.46 | −1.44, 0.149 |
  | 7 | **11.95** | 12.01 | – | 12.48 | −1.40, 0.161 |

  Max-Kp RMSE is lower at every lead (1.115–1.246 vs 1.138–1.260).
- **Skill vs the 27-day mean, days 1–7:** locked **0.122**, live HistGB 0.100 (+22 %); 30-day block bootstrap 95 %
  interval of the difference **[+0.007, +0.050]**, excludes zero.
- **Against NOAA (Ap, days 1–3, the 2,358–2,359 days NOAA issued):** locked 10.66 / 11.82 / 11.67, NOAA 10.89 /
  11.73 / 11.90; Diebold–Mariano p = 0.69 / 0.91 / 0.55. **Level with NOAA: ahead on days 1 and 3, behind on
  day 2, no difference significant.**
  - Scoring bug found while reading the output: one day with no NOAA day-1 forecast made the script's day-1 DM value
    NaN (`diebold_mariano` received the gap). Fixed (approved): NOAA is compared only on the days it issued, and
    `python -m src.forecast.test_locked --rescore` scored the saved forecasts again (nothing refitted or
    re-forecast; every other number identical; `test_scored.json` keeps `first_scored_at`).
- **Storm warnings (thresholds from the 2011–2019 harness only):**

  | Lead | Heidke locked | Heidke live | Detection locked / live | False-alarm ratio locked / live |
  |---|---|---|---|---|
  | 1 | **0.403** | 0.341 | 53 % / 47 % | 54 % / 59 % |
  | 2 | **0.263** | 0.195 | 40 % / 38 % | 65 % / 72 % |
  | 3 | **0.249** | 0.204 | 31 % / 30 % | 62 % / 68 % |
  | 4–7 | 0.206–0.222 | 0.188–0.215 | | |

  Days 1–3 gain +0.058 Heidke on average, with **fewer** false alarms and slightly more storm days caught at every
  one of these leads, unlike the rejected storm experiments (D-72 to D-74), which caught more only by warning more.
- **Adoption rule (D-76):** (a) pooled skill and day-1 RMSE better than the live HistGB: **pass**; (b) storm Heidke
  days 1–3 not lower: **pass** (+0.058); (c) 3 weeks of shadow with working fallbacks: pending.
- **Paper guide (ROADMAP §8, fixed before the test):** level with NOAA and clearly better than the live model →
  **solid paper**, with the coronal-hole features as the contribution.
- **Next:** production fit (`python -m src.forecast.locked_shadow`), shadow run after the push, then adoption.
