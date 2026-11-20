# Tormenta: the whole project, explained

Tormenta forecasts **geomagnetic activity**: how strongly Earth's magnetic field is disturbed by the Sun. It has
two parts:

- a **7-day forecaster**: daily Ap and daily maximum Kp for the next 7 days, with an 80% range and a storm warning,
  issued every morning;
- a **nowcaster**: Kp for the current hour, estimated from the solar wind measured about an hour before it reaches
  Earth.

Everything is scored against the official values from GFZ Potsdam as they arrive, and compared with NOAA's official
forecast.

CT-378 Machine Learning, NED University, Fall 2026 · Alizeh & HRK.

| | |
|---|---|
| Live app | <https://tormenta.streamlit.app/> |
| Code | <https://github.com/Syeda-Aliza-Ayaz/Tormenta> (release v2.0) |
| Model and model card | <https://huggingface.co/aliza-ayaz/tormenta> |
| Every decision, with its reason and result | [DECISIONS.md](DECISIONS.md) (D-01 … D-75) |
| What is planned next | [ROADMAP.md](ROADMAP.md) |

---

## 1. The science in one page

**The Sun** blows a constant stream of charged particles, the **solar wind** (300–800 km/s), carrying its own
magnetic field (the IMF). **Earth's magnetic field** (the magnetosphere) deflects most of it.

**When does it get disturbed?** When the solar wind's field points **south** (negative **Bz**), it connects to
Earth's field and energy pours in. The combination *speed × southward Bz* is the main driver of activity.

**What causes storms?**

| Cause | Effect |
|---|---|
| **CMEs** (clouds of plasma thrown out in eruptions) | the biggest storms, 1–4 days after the eruption |
| **Coronal holes** (dark patches on the Sun that release fast wind) | moderate activity that returns every **27 days** (one solar rotation) |
| **Season** | more activity near the equinoxes (March, September) |
| **11-year solar cycle** | more storms near solar maximum |

**How activity is measured** (by magnetometers on the ground):

| Index | Full name | How often | Scale |
|---|---|---|---|
| **Kp** | planetary K index (K from German *Kennziffer*) | every 3 hours, 8 per day | 0–9 (5 and above = storm) |
| **ap** | planetary amplitude | every 3 hours | 0–400, linear version of Kp |
| **Ap** | daily planetary amplitude | once a day | average of the day's 8 ap values |

The official values come from **GFZ Potsdam**; the most recent days are preliminary and are revised later.
A **storm day** in this project is a day whose highest Kp is at least **5−** (4.67).

---

## 2. The two products

### 2.1 Nowcaster: "what is Kp right now?"

- **Input:** the solar wind measured at the L1 point, 1.5 million km upstream (speed, density, temperature, magnetic
  field |B|, Bx, By, Bz), plus the solar flux F10.7. **No geomagnetic indices are used as inputs.**
- **Features:** 66, all from the past only (coupling functions, pressure, lags, 3–24 h averages, time of day/year).
- **Model:** HistGradientBoosting, plus two quantile models and a correction for an 80% range.
- **Output:** Kp for the current hour, and a short forecast for the next hour (the wind already measured but not yet
  arrived).
- **Training data:** NASA OMNI hourly archive, 1998 onward; labels from GFZ.

### 2.2 Forecaster: "what will Ap and Kp be on each of the next 7 days?"

- **Inputs:** past daily Kp, Ap and F10.7 from GFZ (1947 onward): the last 7 days, 3/7/27-day averages, values one,
  two and three solar rotations back (27, 54, 81 days), F10.7 with flare spikes filtered out, the season.
- **Models issued live:**
  - **HistGB** (headline): 14 separate models, one per lead day (1–7) and target (Ap, max Kp), so an error on day 1
    never feeds into day 2;
  - **storm classifier**: 7 models giving the chance of a storm day, with warning lines tuned for a rare event
    (about 21–31%, not 50%);
  - **ARIMAX**: a classical time-series model, for comparison;
  - **80% ranges** for every model, from their real out-of-sample errors.
- **Reference forecasts** every model must beat: persistence (tomorrow = today), 27-day recurrence, the 27-day
  average, monthly climatology.
- **Issued** every morning by a GitHub job, from GFZ data up to the end of yesterday.

---

## 3. Data

| Data | Source | Used for |
|---|---|---|
| Kp, Ap, F10.7, daily, 1932 → | GFZ Potsdam (kp.gfz.de) | forecaster inputs and every label and score |
| Hourly solar wind, 1998 → | NASA OMNI | nowcaster training; solar-wind experiments |
| Live solar wind | NOAA SWPC (from the DSCOVR/ACE spacecraft) | nowcaster input; solar-wind archive and shadow model |
| NOAA's forecasts (3-day, 27-day, RSGA archive from 2017) | NOAA SWPC | **benchmark only, never an input** |
| CME catalogue | NASA DONKI | experiment D-67 (not adopted) |
| Flare, radio and proton reports, 1996 → | NOAA SWPC event reports | experiment D-74 (not adopted) |
| Daily solar images (AIA 193 Å), 2010 → | SDO, Stanford JSOC archive | experiment D-70 (in progress) |

---

## 4. How the evaluation works (the most important part)

The project is built so that its numbers can be trusted.

1. **Time-ordered splits, never shuffled.** Forecaster: train 1947–2016, validation 2017–2019, **test 2020 – June
   2026**. Nowcaster: train 1998–2016, validation 2017–2019, test 2020 onward. Shuffling time series leaks the
   future into training.
2. **Every choice made on validation only, by a rule written before the run.** The rule says what the change must
   achieve; if it fails, it is dropped, even when part of it looks good.
3. **The test period is scored once**, after every choice is fixed (D-52, re-scored once for a bug fix in D-62).
   It stays closed until the next model is locked.
4. **No future data:** automated tests delete everything after the issue day and check that the forecast does not
   change.
5. **A live log that can never be edited:** every forecast is saved before its day happens, then scored.
6. **Compared with professionals:** NOAA's official forecasts for the same days.

**The yearly validation (D-68)**, used for every improvement since: for each year 2011–2019, train on everything
before that year and forecast the whole year. That gives nine years, a full solar cycle and 362 storm days.

**The keep/drop rule.** A change is kept only if it improves the pooled skill, **wins in at least 6 of the 9
years**, and does not hurt storm warnings. Why 6 of 9: a change that does nothing wins each year roughly by coin
flip; reaching 6 or more of 9 by luck happens about 25% of the time (5 of 9 about 50%), so the bar makes lucky
passes rare while still allowing a real gain to lose a year or two.

**Skill** = the share of the 27-day average's squared error that a model removes. 0 means no better than that
average; negative means worse. **Heidke skill** for storm warnings: 0 = chance, 1 = perfect.

---

## 5. Results

### 5.1 Nowcaster (test 2020 onward, never used for training or choices)

| Model | RMSE (Kp) | R² | RMSE in storm hours |
|---|---|---|---|
| Persistence (previous Kp) | 0.862 | 0.566 | 1.368 |
| Linear regression | 0.665 | 0.742 | 1.470 |
| KNN | 0.657 | 0.748 | 1.337 |
| SVR | 0.605 | 0.786 | 1.079 |
| Random forest | 0.606 | 0.785 | 0.972 |
| **HistGradientBoosting (live)** | **0.573** | **0.808** | **0.846** |

The 80% range contains the real Kp in 80.8% of test hours. Live, against GFZ's quick-look Kp, the error is about
0.59. An equal-weight ensemble (HistGB + random forest + SVR) was a hair better overall but clearly worse on storms,
so HistGB stays alone.

### 5.2 Forecaster (test 2020-01-01 → 2026-06-30, 2,379 days, 325 storm days, scored once)

| Daily Ap error (RMSE) | day 1 | day 3 | day 7 | skill, days 1–7 |
|---|---|---|---|---|
| **HistGB** | **10.78** | **11.91** | **12.01** | **+0.100** |
| NOAA official | 10.89 | 11.90 | – | +0.134 (days 1–3 only) |
| ARIMAX | 10.96 | 12.15 | 12.17 | +0.069 |
| ARIMA | 10.97 | 12.20 | 12.22 | +0.062 |
| SARIMA (27-day season) | 11.11 | 12.43 | 12.49 | +0.025 |
| Chronos-Bolt (pretrained transformer) | 11.83 | 12.66 | 12.65 | −0.015 |
| 27-day average (reference) | 12.27 | 12.45 | 12.48 | 0 |

- HistGB is the best of the project's models at every lead day and **level with NOAA**: ahead on day 1, behind on
  day 2, tied on day 3.
- The 80% ranges hold the real value on 80–81% of days.
- Storm warnings: Heidke 0.19–0.34 across lead days, catching 24–47% of storm days.
- After the test, the live models were refitted on all data up to June 2026 (D-63).

### 5.3 Every model on the same validation days (2011–2019, D-75)

| Model | Ap skill | Ap error, day 1 | Kp skill |
|---|---|---|---|
| **HistGB + solar wind** (candidate, D-68) | **0.112** | **7.42** | **0.124** |
| HistGB (live) | 0.089 | 7.58 | 0.099 |
| GRU (recurrent network) | 0.051 | 7.75 | 0.049 |
| LSTM (recurrent network) | 0.029 | 7.83 | 0.031 |
| Holt-Winters (exponential smoothing) | −0.108 | 8.69 | −0.032 |

Gradient boosting with hand-built features beats the recurrent networks clearly: with about 23,000 daily samples
and few inputs, trees extract more. Holt-Winters is worse than the 27-day average because it follows day-to-day
noise. (These numbers are on 2011–2019, a different period from 5.2, so they are compared with each other, not with
the test table.)

### 5.4 Storm warnings against NOAA (validation 2017–2019, 91 storm days, D-71)

| Heidke skill | day 1 | day 2 | day 3 |
|---|---|---|---|
| NOAA official | **0.41** | **0.38** | 0.32 |
| HistGB (live) | 0.38 | 0.32 | 0.31 |
| HistGB + solar wind | 0.40 | 0.34 | **0.34** |

We catch more storm days than NOAA but raise more false alarms; NOAA, which watches the Sun directly with human
forecasters, is more precise on days 1–2.

---

## 6. What was tried and what happened

Each row had a rule written before it ran. Failures are kept on record on purpose.

| Decision | Idea | Result |
|---|---|---|
| D-41 | ARIMA, SARIMA | ✗ failed (ARIMAX passed and is live) |
| D-46 | Chronos-Bolt pretrained transformer | ✗ failed |
| D-48 | Storm classifier with rare-event warning lines | ✓ live |
| D-64 | Storm-risk recalibration | ✗ failed |
| D-66 | Shorter training history | ✗ rejected (1947 start kept) |
| D-67 | CME catalogue features (DONKI) | ✗ failed |
| D-68 | **Solar wind + 27-day echo + Poisson loss** | ✓ **passed**: Ap skill +27%, Kp +25% (candidate) |
| D-68 | log(Ap) target, retuned storm classifier | ✗ failed |
| D-69 | Stress test of the candidate with live-like data | survives gaps; hurt by biased data and by a feed outage, so a fallback is built in |
| D-72 | Re-forecast today and tomorrow every 3 hours | ✗ failed (tomorrow better in only 5 of 9 years) |
| D-73 | How the issue day ended, as inputs | ✗ failed (false alarms went up) |
| D-74 | Flare, radio and proton warning signs | ✗ failed (false alarms went up) |
| D-70 | Coronal holes from daily solar images | one-year check passed (7–9% lower error 2–4 days ahead); full test in progress |

**The pattern in the storm experiments:** each caught more storms by warning more often, so false alarms never
fell. The remaining false-alarm gap with NOAA probably needs information only NOAA has (direct observation of
eruptions).

---

## 7. The live system

```
GFZ daily file ─┐
NOAA live feeds ┼─► daily GitHub job (src/issue.py), several overnight slots
                │      ├─ issues the 7-day forecast from yesterday's data   ─► forecasts/log.csv   (append-only)
                │      ├─ storm warnings                                     ─► forecasts/storm_log.csv
                │      ├─ scores every forecast whose day has arrived        ─► forecasts/scores.csv
                │      ├─ saves NOAA's forecasts for comparison              ─► forecasts/noaa_live.csv, noaa/
                │      ├─ archives the live solar wind, hour by hour         ─► forecasts/solar_wind_hourly.csv
                │      └─ logs the solar-wind model in shadow mode           ─► forecasts/shadow_log.csv
                └─► commits forecasts/ ─► Streamlit app, Hugging Face Space, model repo
weekly job (retrain.yml): health checks; retrain only after two degraded checks in a row
```

- **Forecasts are never edited and never backfilled.** A forecast exists only if it was issued before its day.
- **Shadow mode:** the solar-wind candidate runs every day next to the live model, is logged and scored, but is not
  shown. If the day's solar wind is missing, it falls back to the live model.
- **Retraining** happens only when live skill drops below a set floor twice in a row, and the new model must beat
  the current one on the newest data.

---

## 8. The app (tormenta.streamlit.app)

| Page | What it shows |
|---|---|
| **Overview** | Kp right now, the next 7 days at a glance, the live solar wind |
| **Forecast** | the 7-day outlook with chart, day cards, storm risk, NOAA's forecast alongside, the live track record |
| **Explore** | replay any past issue day (e.g. the May 2024 superstorm) against what really happened, one forecast and day-before forecasts; or edit the recent days and watch the forecast respond |
| **Scorecard** | every model on the test period, storm tables, report figures, the model health check |
| **Nowcast** | Kp now from the solar wind, the last 5 days against GFZ, live accuracy, a what-if tool |
| **Method** | how the project works and which years were used for what |

Times are shown in Pakistan time (PKT, UTC+5). Light and dark themes.

---

## 9. Known limits

- **Storms from sudden eruptions** leave no trace in past Kp or the solar wind until they arrive, so their first day
  is usually missed (May 2024: the storm onset on 10 May was missed; the next three storm days were warned).
- **Storm size is underestimated:** Kp 9 days are very rare in the training data, so the value forecast stays lower
  (for 11 May 2024 it said 6.0 the evening before; the real value was 9.0). The storm warning is the number to
  trust during storms.
- **The newest days are preliminary** GFZ values; measured revisions change forecasts very little (D-60).
- **The solar-wind model** learned from a corrected archive, while live it reads real-time data; the live check is
  still to be done before adoption.
- A course project, not an operational warning service: for official alerts use NOAA SWPC.

---

## 10. Where things stand and what is next

**Live now (v2.0):** the refitted forecaster, nowcaster, storm warnings, solar-wind archive and shadow model, daily
scoring against GFZ and NOAA.

**Next** (details in [ROADMAP.md](ROADMAP.md)):

1. The full solar-image test (D-70) once the 2010–2019 images are downloaded.
2. Adopt the solar-wind model after weeks of shadow scores, the real-time vs archive check, and the 27-day echo
   being available live.
3. Lock the final model, run the test period once, compare with NOAA with a proper significance test, and write the
   paper.

---

## 11. How the project was built, step by step, and why

Each step lists what was done and the reason recorded at the time. Forecaster steps carry their decision number
(D-NN) in [DECISIONS.md](DECISIONS.md); nowcaster steps are documented in
[docs/PROJECT_NOTES.md](docs/PROJECT_NOTES.md).

### Part 1: the nowcaster (v1 → v3)

| Step | What | Why |
|---|---|---|
| Data: solar wind | NASA OMNI hourly archive, 1998 → 2026-01-10, with placeholder codes (e.g. 9999) turned into "missing" | OMNI is cleaned and time-shifted to Earth; placeholders left in would look like real (impossible) measurements |
| Data: labels | GFZ Kp, the official index, only **definitive** values for training | preliminary values can still change, so learning from them would learn noise |
| Hourly rows, each labelled with its 3-hour block's Kp | | the live app runs at any hour, mid-block; training on whole-block averages would use data the live app does not have yet |
| A complete hourly grid, gaps left as gaps | | "Bz 3 hours ago" must always mean 3 hours; a missing row would silently make it 4 |
| Gap filling and scaling inside the model pipeline | | learned from training years only, so nothing leaks from the test years |
| One shared feature file (`src/features.py`) for training and live use | | training and live can never compute features differently (no train/serve skew); a parity test proves it |
| Features only look backwards; tests check it | | any feature that peeks at the future makes test scores look great and the live app fail |
| No geomagnetic indices as inputs | | the point is to estimate Kp from the solar wind alone; an ablation showed what past Kp would add |
| Physics features (energy coupling, pressure, V·Bs), time of day and season as sin/cos | | they encode how the solar wind couples to Earth's field, including the season effect; sin/cos makes 23:00 sit next to 00:00 |
| F10.7: yesterday's value, flare spikes removed | | today's value is measured at about 20:00 UTC; a flare spike is not the Sun's real activity level |
| Time-ordered splits: train 1998–2016, validation 2017–2019, test 2020+; `TimeSeriesSplit` cross-validation | | shuffled splits leak the future into training for time series |
| Five model families compared (linear, KNN, SVR, random forest, HistGB) | | a fair comparison, tuned the same way, before choosing |
| **HistGB chosen** | | most accurate, small, handles missing values itself (live data has gaps), supports quantile ranges |
| 80% range from quantile models plus a conformal correction | | a single number hides the uncertainty; the correction makes 8 in 10 hours really fall inside |
| v2: 10 features about "where we are in the 3-hour block" (56 → 66 features) | | v1's error was highest in the first hour of each block; kept because CV and validation both improved (rule fixed in advance) |
| v3: storm-memory features and monotonic constraints tried, **rejected** | | they did not improve both CV and validation; the code stays to show what was tried |
| Live: NOAA's propagated solar-wind feed | | the planned feeds had been retired; the new one keeps 7 days and is already time-shifted to Earth, like OMNI |
| Weekly retrain with a gate | | keeps the model fresh; a new model replaces the old only if it is at least as good on 6 held-back months it never saw |
| Deployed: Flask, Streamlit, Hugging Face | | deployment was required; Streamlit Cloud for the full app, Hugging Face for the model and a free in-browser copy |

### Part 2: building the 7-day forecaster

| Decision | What | Why |
|---|---|---|
| D-01 | Forecast 1–7 days ahead and score against official data | the teacher required it; the solar wind only gives about 1 hour of warning, so a new approach was needed |
| D-02 | Past Kp/Ap allowed as inputs, for the forecaster only | nobody knows the solar wind days ahead; beyond a day the information left is past activity, the 27-day rotation and the solar cycle |
| D-03 | Targets: daily Ap and daily max Kp | they are what NOAA forecasts, so we can compare directly; 3-hourly Kp over 7 days would be 56 noisy steps |
| D-04 | The nowcaster stays as its own tab | it is finished and strong, and shows the contrast between seeing the wind and forecasting blind |
| D-05 | One data source: the GFZ daily file | it has Kp, Ap and F10.7 since 1932 (about 8 solar cycles) and is updated daily |
| D-06 | NOAA's forecasts are a benchmark only, never an input | scoring against the official forecast is the strongest scorecard; using it as an input would make our skill borrowed |
| D-07 | A backtest for the evidence, a live log for the demonstration | a 7-day forecast takes 7 days to verify; a week of live data is too little for statistics |
| D-08, D-19 | Same split years as the nowcaster; training from 1947-06-01 | comparable results; 1947 is when the 81-day F10.7 average first exists, so every model starts on the same day |
| D-09 | ARIMAX never sees future input values | using real future values in testing would be leakage that cannot happen live |
| D-10, D-39 | Classical models fitted once, then updated day by day with fixed parameters | refitting at every one of ~2,500 days was too slow, and fixed parameters cannot drift |
| D-11 | The transformer is Chronos-Bolt used as-is | ~34k daily rows is too little to train a transformer; the teacher listed transformers as an option |
| D-12, D-53 | Retrain only when performance drops (two bad weekly checks in a row) | the teacher's rule; skill rather than raw error, because raw error jumps in every storm even when the model is fine |
| D-13, D-26, D-35 | A daily GitHub job with several overnight slots, issuing only from yesterday's data | daily forecasts need daily inputs and scoring; GitHub often starts scheduled jobs hours late |
| D-14, D-15 | Deploy early to Streamlit Cloud and Hugging Face | deployment was required, and finding problems on the last day is the biggest risk |
| D-20 | NOAA and our forecasts lined up by what data each had | comparing "day 1" with "day 1" is only fair if both knew the same data |
| D-21 | Four reference forecasts, including the 27-day average | a model that cannot beat "how active has it been lately" has learned nothing |
| D-22, D-48 | A separate storm classifier with warning lines tuned for rare events | average-value forecasts almost never cross the storm line; resampling was avoided so the probabilities stay honest |
| D-23 | Validation years are a quiet period; kept and reported as a limit | changing the split would break comparability and the test set must not change |
| D-27, D-63 | Live models fitted on a fixed window (to 2019, later to June 2026) | forecasts change only when inputs change, never by silent drift; extended once the test was scored |
| D-30, D-32 | File paths read at run time; models saved from the imported module | tests could otherwise overwrite the real log; a model saved "from `__main__`" would crash the daily job |
| D-31 | HistGB, one model per lead day, tuned on training years, rule: skill > 0 on validation | direct models do not feed on their own errors; nothing chosen by looking at validation or test |
| D-40, D-41, D-42 | ARIMA family: orders by AIC on training years; ARIMAX passes, ARIMA and SARIMA fail | SARIMA had the best AIC but the worst forecasts, because it fell back to the long-run level of busier decades |
| D-45 | 80% ranges for every model from its real out-of-sample errors | the same method for every model, so ranges are comparable |
| D-46 | Chronos fails its rule; kept as a comparison | zero-shot, it was worse than the 27-day average |
| D-47 | F10.7 flare spikes filtered in the forecaster too | a bug: 24 flare days had distorted about 1,900 feature days |
| D-36, D-38, D-54, D-57 | App fixes and the "try the forecaster" page | reported problems (chart hover, live vs what-if mismatch); live inputs were a requirement |

### Part 3: testing once and going live

| Decision | What | Why |
|---|---|---|
| D-51 | Headline models fixed and committed **before** the test | the git history proves the choice was not influenced by the test result |
| D-52 | Test period scored once: 2,379 days, 325 storm days | the one honest measure of how the final models do on unseen years |
| D-59, D-62 | Two bugs fixed (a tuning gap, early-day features); test re-scored once | the fixes came from a code audit before any new test number existed; the re-run is reported whatever it showed |
| D-60, D-61 | Measured: preliminary inputs barely change forecasts; storm chances lean high in quiet years | live forecasts read GFZ's newest, preliminary values, and recent years are quieter than training |
| D-64 | Storm-risk % recalibrated, warnings unchanged | the displayed chance overstated the risk in quiet periods |
| D-65 | Dashboard redesigned | the default Streamlit look did not match the quality of the work |

### Part 4: improving the forecaster (v2.0 onward)

| Decision | What | Why |
|---|---|---|
| D-66 | Shorter training history tried, rejected | recent cycles are quieter; but less history made forecasts worse, so 1947 stays |
| D-67 | NASA's CME catalogue as inputs, rejected | CMEs drive the largest storms, but the catalogue starts in 2014 and added almost nothing |
| D-68 | **A new yearly validation (2011–2019)**; solar wind + 27-day echo + Poisson loss **passes** | one 3-year block in a quiet period was too short to judge small changes; nine years cover a full solar cycle |
| D-69 | Stress test with live-like data; shadow mode and a fallback built | the model learned from a cleaned archive but would read the raw live feed; a feed outage must not make forecasts worse |
| D-70 | Coronal holes from daily solar images: rules first, small trials, full test in progress | coronal holes send fast wind 2–4 days ahead, exactly where the forecaster is weakest |
| D-71 | Storm warnings measured against NOAA's | to know what "good" looks like before any storm work: our weak spot is false alarms |
| D-72 | Re-forecast today and tomorrow every 3 hours, rejected | today improved in all 9 years but tomorrow in only 5 of 9; adopting only the good half after seeing the results would be cheating |
| D-73 | How the issue day ended, as inputs, rejected | it caught more storms but raised false alarms, the opposite of its aim |
| D-74 | Flare, radio and proton warning signs, rejected | same pattern: more catches, more false alarms; scored on quiet years where eruptions are rare |
| D-75 | Holt-Winters, LSTM and GRU compared on the same days | for the report: gradient boosting beats both recurrent networks, and Holt-Winters is worse than the 27-day average |

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **Lead day** | how many days ahead a forecast is: day 1 = tomorrow, day 7 = a week ahead |
| **Issue day / origin** | the last day of data a forecast used |
| **Skill** | share of the 27-day average's error removed (0 = no better, negative = worse) |
| **RMSE / MAE** | root-mean-square / mean absolute error (lower is better) |
| **Heidke skill** | how much better storm warnings are than chance (0 = chance, 1 = perfect) |
| **Brier score** | how accurate storm probabilities are (lower is better) |
| **False-alarm ratio** | share of warnings that did not end in a storm |
| **80% range** | a band that should contain the real value on 8 days in 10 |
| **27-day echo / recurrence** | activity repeating one solar rotation later |
| **Shadow mode** | a model runs and is scored live but is not shown |
| **Leakage** | information from the future reaching a model in training or testing |
| **HistGB** | histogram-based gradient boosting (many small decision trees, each correcting the last) |

## 13. Where to read more

| File | Contents |
|---|---|
| [README.md](README.md) | setup, how to run, repository layout |
| [DECISIONS.md](DECISIONS.md) | every decision: what, why, the rule, the result |
| [ROADMAP.md](ROADMAP.md) | open work, in order, with checklists |
| [PLAN.md](PLAN.md) | the original v2 forecaster plan |
| [docs/PROJECT_NOTES.md](docs/PROJECT_NOTES.md) | what each file does and why |
| [TODO.md](TODO.md) | work blocked by network access or waiting for data |
