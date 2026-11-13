# Tormenta v2: from nowcaster to 7-day forecaster

**Status:** planning · **Window:** Tue 10 Nov → ~Fri 20 Nov 2026 (about 1.5 weeks)
**Team:** Alizeh, HRK · CT-378 Machine Learning, NED University

The nowcaster (v1, built from [TORMENTA_BUILD_PLAN.md](TORMENTA_BUILD_PLAN.md)) is finished and stays as it is.
This plan adds a forecaster on top of it. Every decision and its outcome is logged in [DECISIONS.md](DECISIONS.md).

---

## 1. What the teacher asked for

| # | Requirement | Where it is covered |
|---|---|---|
| R1 | Forecast at least 1 week ahead | §2, §5, §6 |
| R2 | Use ARIMA / SARIMA / ARIMAX / transformers | §6 |
| R3 | Score our forecasts once official data arrives, and show scorecards | §7, §8 |
| R4 | Inputs the teacher can type in to see the model work live | §10 |
| R5 | Retrain only when the model performs badly | §9 |

---

## 2. Key decisions

- **Target:** daily **Ap** (0–400) and daily **max Kp** (0–9), for **lead days 1–7**.
  These are the same quantities NOAA forecasts, so we can score ourselves directly against the official forecast.
- **Issue time:** once per day, after GFZ has published day D. The forecast covers days D+1 … D+7.
  It uses only data up to the end of day D (the leakage rule, enforced by a test).
- **Inputs:** past Kp/Ap and F10.7. **Geomagnetic indices are now allowed as inputs, but only for the forecaster.**
  The nowcaster rule ("no indices as inputs", old plan §0.1) still applies to the nowcaster.
  - *Why this changes:* we cannot know the solar wind several days ahead, so beyond about 1 day the only
    useful information is past activity, the 27-day solar rotation, and the solar cycle.
  - *Viva framing:* past Kp is autoregression, not leakage. The forecaster must beat persistence and
    27-day recurrence to be worth anything.
- **Split:** the same years as before, with more history available:
  - train: 1947-06-01–2016 (F10.7 starts in 1947; DECISIONS D-19)
  - validation: 2017–2019
  - test: 2020 → last definitive day (about Jun 2026)
  - The test set is scored once per model version.
- **Expected skill:** honest framing. Skill should be useful on days 1–2 and close to the recurrence/climatology
  baselines by days 5–7. Storms caused by coronal mass ejections (CMEs) cannot be forecast from a time series.
  The headline result is **how skill decays with lead time compared with the baselines and NOAA**, not
  "accurate at 7 days".
- **Nowcaster:** kept as hour 0 and as its own app tab. No rework.

---

## 3. Data sources

**No new input sources are needed.** The GFZ file we already download is updated **every day**. It contains
3-hourly Kp, daily Ap and observed F10.7 from 1932 up to yesterday (checked 10 Nov 2026: the last row is 9 Nov).
Each row carries a quality flag:
- `D=2` definitive (currently up to about Jun 2026)
- `1` provisional
- `0` nowcast (the most recent days)

The only new source is NOAA, and **only as a benchmark**, never as a model input.

| Role | Source | Cadence | Status |
|---|---|---|---|
| Training data + forecast inputs + verification | GFZ `Kp_ap_Ap_SN_F107_since_1932.txt` | daily | **have**: also keep the `Ap` column ([fetch_gfz.py:36](src/ingest/fetch_gfz.py#L36) drops it) and add daily max Kp |
| Today's partial Kp (live input / scoring) | GFZ `Kp_ap_nowcast.txt` | every 3 h | **have** |
| F10.7 when GFZ is late | SWPC `10cm-flux-30-day.json` | daily | **have** |
| Solar wind (nowcaster only) | SWPC propagated solar wind; OMNI2 | live / months behind | **have** |
| **NOAA days 1–3 forecast, historical** | SWPC FTP `ftp.swpc.noaa.gov/pub/warehouse/<year>/<year>_RSGA.tar.gz`: one report per day, line `Predicted Afr/Ap` (Ap for D+1..D+3) | daily, archived | **new**: checked 10 Nov, the 2025 tarball has 364 daily reports |
| **NOAA days 1–27 outlook, live** | `services.swpc.noaa.gov/text/27-day-outlook.txt` (daily Ap + max Kp) | weekly issue | **new**: **not** in the warehouse archive, so we save a copy daily from now on |
| NOAA days 1–3 forecast, live | `services.swpc.noaa.gov/text/3-day-forecast.txt` (3-hourly Kp) | daily | **new**: save daily |

What follows from this:
- Against NOAA, **days 1–3 are scored over the whole backtest** (from the RSGA archive).
- **Days 4–7 are compared only from the day we start saving the outlook.**
- The GitHub runner must be able to reach the SWPC FTP server. If it can't, we run the RSGA backfill once
  locally and commit the parsed CSV (it is small).

**Training/serving gap to note:** the model trains on definitive Kp, but live inputs for the last few days come
from provisional/nowcast Kp. This is a real operating condition, not leakage. We record it and, if time allows,
measure it.

---

## 4. Leakage and integrity rules

1. A forecast issued at the end of day D uses only rows at or before D. A test shifts the data and asserts
   the features do not change.
2. **ARIMAX exogenous inputs** are never future values. F10.7 for D+1..D+7 is the last known value carried
   forward (it changes slowly), the same in the backtest and live.
3. Backtest uses a **rolling origin**: one forecast per day, each built only from data available on its issue date.
4. **The live log is append-only.** Forecasts are committed on the day they are issued and never edited.
   A test checks that existing rows are unchanged. Past dates are **never** backfilled into the live log;
   that is what the backtest is for.
5. Scores use **definitive** Kp when available, and otherwise provisional Kp marked as such. A score is
   recomputed when the definitive value arrives.

---

## 5. Features (shared by training, backtest and live, in one module)

For issue day D, all trailing:
- Ap and max Kp on days D, D−1 … D−6; 3- and 7-day means; maximum Kp over 7 days
- **27-day recurrence:** Ap on days D+h−27, D+h−54 and D+h−81 for each lead day h (all in the past while h ≤ 7 < 27),
  and their mean
- F10.7: day D value and 81-day trailing mean (reuse the existing logic)
- Day of year as sin/cos (storms are more common near the equinoxes); solar-cycle phase from the 81-day F10.7
- *Ablation, only if time:* lagged daily-mean solar wind (OMNI, 1963+, gappy). Expected to help only day 1.

---

## 6. Models

| Model | Setup | Notes |
|---|---|---|
| Persistence | Ap(D+h) = Ap(D) | baseline |
| 27-day recurrence | Ap(D+h) = Ap(D+h−27) | baseline; the one NOAA's outlook is largely built on |
| 27-day trailing mean | mean of the last 27 days | baseline; the strongest one on validation (D-21) |
| Climatology | training-period mean for the target day's calendar month | baseline |
| ARIMA | on log(1+Ap) | order picked by AIC on train |
| SARIMA | seasonal period 27 days | fit once on train, then extend the state with new data at each origin without refitting (otherwise the backtest is too slow) |
| ARIMAX | ARIMA + F10.7 81-day mean + recurrence term as exogenous inputs | exogenous inputs per §4.2 |
| **HistGB, one model per lead day** | §5 features; quantile models for the interval | likely the strongest; reuses the existing pipeline |
| Chronos-Bolt (pretrained transformer) | zero-shot on log(1+Ap) | the transformer the teacher mentioned. Needs `torch`: the CPU-only build plus Chronos-Bolt-small should fit Streamlit Cloud (about 2.7 GB maximum memory). Fallback: the app shows the forecast the daily job saved (§10) |
| *Stretch:* small transformer we train ourselves | — | only if days 3–5 finish early |

**Intervals:** 80% for every model, from validation residuals per lead day (the same method for all, so
coverage is comparable).

**Production model:** chosen on validation skill averaged over lead days 1–7, by a rule written down before
looking at test.

---

## 7. Evaluation (backtest scorecard)

Rolling-origin backtest over validation and over test. For each model and each lead day 1–7:
- RMSE and MAE (Ap and max Kp)
- **Skill score** = 1 − MSE_model / MSE_reference, with persistence, recurrence and climatology as references
- **Storm days** (max Kp ≥ 5−, i.e. ≥ 4.667): probability of detection (POD), false alarm ratio (FAR),
  Heidke skill score (HSS)
- 80% interval coverage
- **NOAA comparison:** days 1–3 over the whole backtest (RSGA); days 1–7 live (27-day outlook)

Main figures:
- skill vs lead day, one line per model
- error by activity level
- a case study of the May 2024 storm (forecast issued 1–7 days before)

---

## 8. Live forecast log and verification

Daily GitHub Actions job (`daily.yml`, about 02:00 UTC):
1. Download GFZ. Stop with a warning (no failure) if day D is not there yet.
2. Issue the D+1..D+7 forecasts from every model, then append them to `forecasts/log.csv`. Columns:
   `issued, model, lead, target_date, ap, ap_lo, ap_hi, kpmax, kpmax_lo, kpmax_hi, model_version`.
3. Save NOAA's 27-day outlook and 3-day forecast to `forecasts/noaa/`.
4. Score every logged forecast whose target day now has GFZ data. Write `forecasts/scores.csv`, with a
   `definitive` flag on each row.
5. Commit. Streamlit Cloud redeploys on the push.

**Timing:** a 7-day forecast takes 7 days to verify. **The job must be running by day 2 (12 Nov).**
Even then, only forecasts issued 12–13 Nov will be scored at lead day 7 by the deadline. The live log
demonstrates the system; the backtest is the statistical evidence.

---

## 9. Retraining only when performance drops

**Today:** [update.py](src/update.py) retrains every Monday whenever there is new data, and the gate decides
whether to promote. Nothing checks whether the current model is actually doing badly.

**New rule (`src/monitor.py`, weekly):**
1. From `scores.csv`, compute the 28-day rolling **skill score against persistence** for lead days 1–3.
   - We use skill, not raw RMSE, because raw error jumps in every storm even when the model is fine.
     Persistence suffers in storms too, so skill stays stable unless *our* model gets worse.
2. Flag the model as **degraded** if the skill is below its backtest level minus a margin, or below 0.
   The margin is set from the spread of 28-day skill in the backtest.
3. Retrain only after **two degraded checks in a row**. The existing gate still decides promotion, and the
   reason for the retrain is logged in `metrics_history.json`.
4. The nowcaster gets the same treatment: the daily job also logs yesterday's 24 hourly nowcasts (SWPC holds
   7 days of solar wind) and scores them against GFZ, and its weekly retrain runs only when degraded.
   *Drop this item if time runs short.*

The test for this injects degraded scores and checks that the retrain fires, and only after the second
degraded check. For the remaining weeks the monitor will almost certainly report "healthy". That is the
expected result.

---

## 10. App and deployment (required)

### Tabs (one Streamlit app, used by both hosted deployments)

| Tab | Content |
|---|---|
| **7-day forecast** | today's forecast from every model, with intervals, NOAA overlaid, and the storm risk per day |
| **Try it yourself** | (a) **Edit inputs:** a table of the last 30 days of Ap/max Kp and F10.7, pre-filled with live data and editable; presets (quiet, recurrent storm, big storm); every model reforecasts instantly. (b) **Pick a past date:** forecast as if issued that day, overlaid with what actually happened |
| **Scorecard** | live log: forecast vs actual, error per lead day, the NOAA comparison. Backtest: skill vs lead day, storm table. Model health: rolling skill, threshold, last retrain and reason |
| Live nowcast | the existing tab, unchanged |
| About | updated methods |

### Where each part runs

Hosted Gradio/Docker Spaces on Hugging Face need PRO (we got a 402 error in Phase 5). So the free options are
Streamlit Cloud (a real server) and a static HF Space (the app runs in the visitor's browser).

| Deployment | What runs there | Chronos |
|---|---|---|
| **GitHub Actions daily job** (batch serving) | every model issues the official daily forecast, scores the old ones, then commits | runs (torch installed in the job) |
| **Streamlit Cloud** (main, already live) | the whole app: every model forecasts live from the teacher's inputs; scorecards read `forecasts/*.csv` from the repo | live, with the CPU-only torch build + Chronos-Bolt-small, loaded once and cached. If it exceeds memory: show the forecast the daily job saved, labelled as such |
| **HF static Space** (stlite, in the browser) | the same app. Baselines in numpy; HistGB per lead day as portable `.npz` (extend [portable.py](src/portable.py)); ARIMA family with statsmodels in the browser (Pyodide) | saved forecast only (no torch in the browser) |
| **HF model repo** | forecaster bundles + updated model card | — |
| **Flask** (local) | add a `/forecast` page and a `/api/forecast` JSON endpoint | saved forecast |

**Rules:**
- **Deploy early.** A forecast tab that reads `log.csv` goes live on Streamlit on day 2, and every later step
  redeploys.
- The app must **never crash when a model is unavailable**. It shows "unavailable here" and moves on (the same
  pattern the nowcaster uses for a missing feed).
- The daily job publishes to the HF Space and model repo (`sync_hf.py`), just as the weekly job does now.

---

## 11. New and changed files

```
src/ingest/fetch_gfz.py      keep Ap; daily max Kp
src/ingest/fetch_noaa.py     NEW: RSGA archive parser, 27-day outlook + 3-day forecast parsers
src/daily.py                 NEW: daily table (Ap, max Kp, F10.7, quality flag) from GFZ
src/forecast/                NEW: features.py (§5), baselines.py, arima.py, gbm.py, chronos_model.py, registry.py
src/backtest.py              NEW: rolling-origin runner
src/scorecard.py             NEW: metrics, skill scores, storm table (POD/FAR/HSS)
src/issue.py                 NEW: daily job (issue, save NOAA, score)
src/monitor.py               NEW: degradation check → retrain decision
src/update.py                changed: retrain only if monitor says so
forecasts/                   NEW: log.csv, scores.csv, noaa/   (committed, append-only)
.github/workflows/daily.yml  NEW
.github/workflows/retrain.yml changed: monitor first
notebooks/07_forecasting.ipynb  NEW: EDA (autocorrelation, 27-day recurrence), model comparison, backtest figures
app/streamlit_app.py         new tabs (§10); graceful fallback when a model is unavailable
src/portable.py              extend: per-lead-day HistGB → .npz for the browser Space
app/hf_space/sync_hf.py      add the forecaster files, forecasts/*.csv and the browser packages (statsmodels)
app/flask_app/               /forecast page + /api/forecast
tests/                       forecast leakage, append-only log, NOAA parsers, monitor trigger, daily-job dry run,
                             app smoke tests with and without Chronos
requirements.txt             + statsmodels, CPU-only torch (via --extra-index-url), chronos-forecasting, all exact pins
```

---

## 12. Timeline

| Day | Date | Work | Done |
|---|---|---|---|
| 1 | Tue 10 Nov | Re-download raw data; `daily.py`; keep Ap; baselines; NOAA parsers (RSGA + live) | [x] |
| 2 | Wed 11 Nov | `issue.py` + `daily.yml` with the baselines, **so the live log starts**; RSGA backfill; **a basic forecast tab live on Streamlit, reading `log.csv`** | [x] (done 10 Nov; RSGA done on day 1) |
| 3 | Thu 12 Nov | Forecast features (§5) + leakage test; HistGB per lead day; backtest runner | [x] (done 10 Nov) |
| 4 | Fri 13 Nov | ARIMA / SARIMA / ARIMAX | [x] (done 12 Nov; ARIMAX passes, ARIMA/SARIMA fail) |
| 5 | Sat 14 Nov | Chronos; intervals for all models; add every model to the daily job; **test CPU torch + Chronos on Streamlit Cloud** (decides live vs saved) | [x] (done 13 Nov; ranges live, Chronos fails its rule, no Streamlit torch needed) |
| 6 | Sun 15 Nov | Scorecards + figures; choose the production model by the fixed rule; score test once | [ ] |
| 7 | Mon 16 Nov | Streamlit: 7-day forecast tab + Try it yourself (edit inputs, past date); deploy | [ ] |
| 8 | Tue 17 Nov | Streamlit: scorecard tab + model health; deploy. HF: portable per-lead HistGB, browser Space, model repo + card | [ ] |
| 9 | Wed 18 Nov | `monitor.py`, trigger-based retrain, tests; Flask `/forecast` | [ ] |
| 10 | Thu 19 Nov | README, PROJECT_NOTES, report + viva notes; repo cleanup (§14); check every deployment end to end | [ ] |
| — | Fri 20 Nov | Buffer | [ ] |

**Order of priority if we fall behind:** live log running (day 2) → Streamlit deployment of the forecaster →
HistGB + ARIMA + backtest scorecard → input UI → SARIMA/ARIMAX → Chronos → monitor → HF Space forecaster →
Flask → nowcaster monitoring. Our own transformer is dropped unless everything else is done.

---

## 13. Risks

| Risk | Mitigation |
|---|---|
| SARIMA(27) slow in the rolling backtest | fit once, extend the state per origin; if still slow, refit weekly |
| Chronos + torch exceed Streamlit Cloud memory, or the install is too slow | CPU-only torch build, the smallest Bolt model, loaded once and cached; fallback to the saved daily forecast, labelled in the app |
| statsmodels is slow or missing in the browser Space | serve the saved ARIMA-family forecasts there; live recompute stays on Streamlit |
| Streamlit Cloud redeploys on every daily commit (a short outage each day) | acceptable; the job runs at about 02:00 UTC (07:00 in Pakistan), before anyone uses the app |
| GitHub runner blocks the SWPC FTP server | backfill RSGA locally once and commit the CSV |
| GFZ publishes day D late | the job skips that day with a warning; GitHub cron can also run late |
| Daily commits make the history noisy | one bot commit per day, small CSV changes only |
| Too few live scores for statistics | present the live log as a demonstration; the backtest carries the statistics |

---

## 14. Cleanup (day 10)

- Remove `reports/v2/` files that are byte-identical copies of `reports/figures` and `reports/metrics` (18 pairs).
- Remove `reports.zip` and `docs/report/overleaf_upload.zip` (rebuild when needed).
- Keep only `current.joblib` plus the latest version of each model; git history keeps the rest.
- Add a "v2 forecaster" header to `docs/PROJECT_NOTES.md`. Update the README framing from nowcast to forecast + nowcast.
