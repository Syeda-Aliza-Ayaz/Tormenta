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
