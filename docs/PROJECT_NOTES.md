# Tormenta — Project Notes

**Team:** Alizeh, HRK · **Course:** CT-378 Machine Learning, NED University (Fall 2026)

A running, plain-language log of every file in the project: **what** it does, **how**, **why**, and **what we got from it**. Updated as each phase is built. The detailed, report-ready version (data sources, variable glossary, physics, viva notes) is [`report_notes.tex`](report_notes.tex).

**Status:** Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅ · Phase 3 ✅ (v1) · Phase 3b ✅ (v2 promoted to production) · Phase 3c ✅ (final model v3 = v2 + calibrated intervals; **frozen**) · Phase 4 ✅ (live nowcast) · Phase 5 ✅ (Flask local · Streamlit https://tormenta.streamlit.app/ · HF model repo + static Space) · Phase 6 ✅ (weekly retrain on GitHub Actions; dry run passed) · Phase 7 ⬜

---

## The project in one paragraph

The Sun constantly blows charged gas (the **solar wind**) toward Earth. A satellite at the L1 point, about 1.5 million km sunward, measures it roughly 30–60 minutes before it hits us. When the wind is fast and its magnetic field points **south**, it shakes Earth's magnetic field and causes a **geomagnetic storm**, which can disrupt GPS, radio, satellites and power grids. The **Kp index** (0–9) measures how strong that shaking is. **Tormenta** is a regression model that reads the satellite measurements and estimates the current Kp (a *nowcast*).

---

## Phase 0 — Project setup

### `.gitignore`
- **What:** tells Git which files *not* to track.
- **How:** lists the virtual environment, raw data, processed data and Python cache folders.
- **Why:** raw data can be re-downloaded and processed data is rebuilt by code, so committing them would bloat the repository. The weekly auto-retrain would otherwise commit tens of MB every week.
- **Result:** the repo holds only code, docs, small files and (later) the model.

### `src/config.py`
- **What:** one central place for every path, column name and constant.
- **How:** plain Python variables: file paths, the OMNI column list, the per-column "missing value" codes, split years, Kp storm bins, SWPC URLs, training settings.
- **Why:** if a number lives in one place, the training code and the live apps can't drift apart. Changing the split years, for example, is a one-line edit.
- **Result:** every other file imports `config` instead of hard-coding values.
- **Notable choices:**
  - The OMNI missing-value codes (`999.9`, `9999999.`, …) were **checked against the actual file** and all matched NASA's documentation.
  - **Storm bins follow NOAA rounding.** Kp comes in thirds, so "5−" = 4.67 already counts as a G1 storm. Bin edges sit at 3.5, 4.5, 5.5, 6.5.
  - F10.7 comes from GFZ's *observed* value, the same quantity NOAA serves live.

### `requirements.txt` / `requirements-dev.txt`
- **What:** the exact package versions the project needs.
- **How:** `requirements.txt` holds what the apps need (numpy, pandas, scikit-learn 1.9.1, …). `requirements-dev.txt` adds notebook and testing tools.
- **Why:** a saved scikit-learn model can break or misbehave if loaded under a different scikit-learn version. Pinning guarantees training and all three deployments use the same one.
- **Result:** Python **3.12** environment (`.venv`), registered in Jupyter as the kernel **"Python 3.12 (tormenta)"**.
- **Why 3.12 and not 3.14:** Streamlit Community Cloud defaults to 3.12, and there are forum reports of apps breaking on 3.14. Hugging Face also supports 3.12. Matching versions everywhere avoids surprises.

### Folder layout
`data/raw` (downloads) · `data/processed` (built table) · `src/` (all logic) · `notebooks/` (run and inspect) · `models/` · `app/` · `reports/figures/` · `docs/` · `tests/`.
All logic lives in `src/`, and the notebooks only *call* it. This lets the live apps reuse exactly the same code (no train/serve skew).

---

## Phase 1 — Getting the data ready

### `src/ingest/fetch_omni.py`
- **What:** reads NASA's OMNI2 hourly solar-wind file into a table.
- **How:**
  1. Reads the space-separated file and names the 17 columns.
  2. Replaces each column's placeholder code (e.g. `9999.` for speed) with "missing" (NaN).
  3. Builds a real timestamp from year + day-of-year + hour.
- **Why:** if left in, the placeholders would look like real measurements (e.g. a 9999 km/s wind) and wreck the model.
- **Result:** 245,688 hourly rows, **1998-01-01 → 2026-01-10**.
- ⚠️ **Correction:** we first misread the file's last line `2026 10 22` as October 22. It is actually **day-of-year 10, hour 22**. OMNI data lags real time by *months*, not days.

### `src/ingest/fetch_gfz.py`
- **What:** reads the Kp index from GFZ Potsdam (our "answer key").
- **How:**
  1. The file has one row per day with 8 Kp values (one per 3-hour block).
  2. We "melt" these into one value per block with proper start times (00, 03, …, 21 UT).
  3. We keep the **definitive flag** (`D = 2` means final; 0/1 means preliminary and may still change).
  4. We also read the daily observed F10.7.
- **Why:** Kp is the target the model learns to predict. Preliminary values can change, so we only train on final ones.
- **Result:** a 3-hourly Kp series from 1932, plus daily F10.7.

### `src/preprocessing.py`
- **What:** merges solar wind and Kp into one hourly modelling table and checks it.
- **How:**
  1. **Complete hourly grid:** every hour from 1998 to 2026 gets a row, even if empty.
  2. **Label:** each hour gets the Kp of the 3-hour block it falls in (22:00 → the 21:00–24:00 block).
  3. Attaches the definitive flag and the daily F10.7; drops the sunspot number and OMNI's F10.7.
  4. **Sanity checks:** no duplicate times, no holes in the grid, Kp always between 0 and 9.
  5. Saves the table, plus a small F10.7 history file (last 365 days) for the live app.
- **Why:**
  - *Complete grid:* later we compute "Bz 3 hours ago" by stepping back 3 rows. If an hour were missing, that would silently become 4 hours.
  - *Hourly cadence:* the live app runs at any hour, mid-block, so training must look like that too. The original plan of averaging over whole 3-hour blocks would have used data the live app doesn't have yet.
- **Result:** `data/processed/tormenta_hourly.csv`, with 245,688 rows and 15 columns.
  - Every row has a definitive label: about **82k independent 3-hour labels**, since three hourly rows share one Kp.
  - Missing data is at most 2.3% in any column (density, temperature), and 0.16% for Bz.
- **Deliberately *not* done here:**
  - Filling gaps and scaling: these go inside the model pipeline and are learned from training years only, so no information leaks from the test years.
  - Derived physics features: these go in `features.py` so the live app uses identical code.

### `notebooks/01_preprocessing.ipynb`
- **What:** runs the steps above and shows the results.
- **Result:** the printed summary, missing-% table and a May 2024 spot check (Bz −35 nT, ~740 km/s, Kp 9).

### `data/f107_history.csv`
- **What:** the last year of daily F10.7 values.
- **Why:** the live app needs an 81-day trailing average. Reading a small file is more reliable than fetching 81 days from NOAA on every prediction. The weekly retrain refreshes it.

---

## Phase 2 — Exploratory Data Analysis

### `notebooks/02_eda.ipynb`
- **What:** 8 plots and tables that answer "what does our data look like, and what drives Kp?"
- **How:** pandas + matplotlib. Figures are saved to `reports/figures/`. Relationships that guide modelling decisions are computed on the **training years only** (1998–2016).
- **Why:** to understand the data before modelling, justify our feature choices with evidence, and find problems (gaps, outliers) early.

**What we found:**

| # | Figure | Finding | What it means for us |
|---|---|---|---|
| 1 | `01_kp_distribution` | Storms (Kp ≥ 5−) are only **4.1%** of hours; G3+ storms are ~0.5% | Heavy imbalance → the model will tend to under-predict storms. Report error by storm level and test sample weighting. |
| 1b | (table) | The **validation years 2017–2019 are solar minimum**: only 0.09% G3+ hours vs 0.5% in train/test | Val alone is a weak judge of storm performance. Also look at storm-level errors and CV scores when choosing models. |
| 2 | `02_input_distributions` | Density and temperature are strongly right-skewed (log-normal-ish); Bz is centred on 0 | Fine for tree models; scaling matters for KNN/SVR. A log transform is an option. |
| 3 | `03_missingness` | Plasma (density/temperature) is worst, ~12% missing in 2000–2002 (ACE instrument era). All fields have a gap in 2021 | Gaps are uneven across years. |
| 3b | (gap table) | Half of density gaps are ≤3 h, but **52% of missing density hours sit in gaps > 24 h** | Simple interpolation won't cover long gaps. HistGB's built-in handling of missing values is the right production choice. |
| 4 | `04_kp_vs_drivers` | Kp rises steadily as Bz goes negative, as speed rises, and as V·Bs rises. Northward Bz raises Kp much less | Confirms the physics: southward field + fast wind = storms. |
| 5 | `05_correlation` | Spearman ρ with Kp: speed 0.58, temperature 0.55, \|B\| 0.55, V·Bs 0.41, Bz −0.33; Bx/By ≈ 0 | Speed and field strength are the strongest single signals. Bx/By alone are weak (but By matters inside the clock angle). |
| 6 | `06_lag_correlation` | V·Bs correlates best **1 hour earlier** (0.43), fading by 6–9 h. Speed keeps memory for a day (0.26 at 24 h) | Supports the 1/3/6/9 h lags. Suggests adding a **longer (12–24 h) speed average**. |
| 7 | `07_solar_cycle` | Activity follows the ~11-year solar cycle. 2003 is the most active year (Halloween storms); 2009 and 2019–2020 are quietest | Train covers cycles 23–24, test covers the rise of cycle 25. |
| 8 | `08_may2024_storm` | The CME arrives (speed jumps 450 → 700+ km/s, density spikes), Bz swings to −35 nT, Kp reaches 9 | A clear, held-out extreme event to stress-test the model. |
| 9 | (extremes table) | 87% of \|Bz\| > 30 nT hours and 92% of speed > 900 km/s hours happen during storms (baseline 4%) | Extremes are **real physics, not errors**, so we keep them. |
| 10 | (F10.7 check) | 7 daily F10.7 values > 400 (max 938, 2011-03-07): flare-contaminated measurements | To handle in Phase 3 (e.g. flag values far above the trailing median). |

**Open decisions this creates for Phase 3:**
1. Add 12 h / 24 h trailing speed means. This needs ≥ 33 h of live history, so the live app would use NOAA's 3-day feed.
2. Clean F10.7 flare spikes.
3. Account for the quiet validation period in model selection.

---

## Phase 3 — Features & modelling

### `src/features.py` (the most important file in the project)
- **What:** turns raw hourly solar-wind readings into the **56 clues** (features) the model learns from.
- **How:** one function, `build_features(hourly, f107_daily)`, builds six groups:

  | Group | Count | Examples | Plain meaning |
  |---|---|---|---|
  | Raw | 7 | `bz_gsm`, `speed`, `density` | The satellite readings themselves |
  | Derived physics | 8 | `pressure`, `vbs`, `newell`, `beta` | Physics formulas that combine readings (e.g. "how much energy gets in") |
  | Lags | 16 | `bz_gsm_lag3h`, `vbs_lag1h` | What the wind was doing 1, 3, 6, 9 hours ago |
  | Rolling stats | 19 | `speed_mean24h`, `bz_gsm_std6h`, `bz_min3h` | Recent averages, wobbliness, extremes |
  | F10.7 | 2 | `f107_prev`, `f107_mean81d` | Yesterday's solar brightness and its ~3-month average |
  | Time | 4 | `hour_sin`, `doy_cos` | Time of day and season, as points on a circle |

- **Why it's built this way:**
  - **Used by both training and the live app**, so the two can never compute features differently (no train/serve skew).
  - **Only looks backwards:** every feature at hour *t* uses data from *t* or earlier. Rolling windows are trailing, never centred.
  - **Complete hourly grid first** (`asfreq("h")`), so a 3-hour lag is always exactly 3 hours.
  - **Physics is recomputed from raw readings**, because NOAA's live feed doesn't include OMNI's ready-made columns.
  - **The 12 h / 24 h speed averages** were added because EDA showed speed matters for about a day.
  - **The F10.7 value** is *yesterday's*, because today's is measured at about 20 UT. Flare spikes (more than 2× the median of the previous 27 days) are removed.
  - **Time-of-day and season** matter physically: Earth's magnetic tilt changes how well the solar wind couples (the Russell–McPherron effect). Sin/cos makes 23:00 sit next to 00:00.
- **Result — check against OMNI's own columns:**
  - Our E-field, beta and Mach number match OMNI's exactly (ratio 1.000).
  - Our pressure is 0.88 × OMNI's, a constant ratio, because we deliberately leave out the alpha-particle term (live data has no alpha measurements).

### `tests/test_features.py`
- **What:** 4 automatic tests, run with `pytest`.
- **How and why:**
  1. **Causality:** features at time *t* don't change when future rows are added. This proves there's no leakage from the future.
  2. **Gaps:** deleting rows doesn't shift the lags. A 3-hour lag stays 3 hours.
  3. **F10.7:** flare spikes are removed, and only yesterday's value is used.
  4. **No storm indices as inputs, and more than 15 features.**
- **Result:** all 4 pass. These tests catch the "silent" bugs that would otherwise make the scores look great and the live app fail.

### `src/train.py`
- **What:** the full training recipe, run step by step from the notebook.
- **How:**
  1. `load_xy`: builds the features and keeps only hours with a final (definitive) Kp. Also builds the **persistence baseline** ("Kp = the previous block's Kp").
  2. `split_masks`: train 1998–2016, validation 2017–2019, test 2020–2026.
  3. `tune_models`: each of Linear Regression, KNN, SVR, Random Forest and HistGB gets a **randomised search** over its settings, scored by `TimeSeriesSplit(5)`. Each fold trains on earlier years and checks on later ones.
     - KNN and SVR use every 9th hour (~18k rows), because SVR gets very slow on big data.
     - Random Forest is tuned on every 3rd hour, then retrained on all hours.
  4. `validation_table`: validation scores, CV scores and training scores side by side, to judge **over- and underfitting**.
  5. `test_evaluation`: every model is retrained on train+val and tested **once** on 2020–2026.
  6. `weighting_ablation`: HistGB with vs without extra weight on storm hours (`1 + Kp/3`).
  7. `fit_production`: the final HistGB, plus two "quantile" HistGBs that give an **80% range** (10th–90th percentile), trained on all data **except the last 6 months**. Those months are kept as the check for the weekly retrain.
  8. `save_bundle`: saves `models/tormenta_vYYYYMMDD.joblib` and `current.joblib`, and logs the scores to `models/metrics_history.json`.
- **Why HistGB for production:** accurate, small file, copes with missing values by itself (important, because live data has gaps), and supports quantile ranges.
- **Smoke test (fast mode, tiny search, not final numbers):**
  - HistGB test RMSE 0.63 vs persistence 0.86.
  - Storms are still under-predicted (G3+ bias about −0.75 Kp).
  - The 80% range covered only ~69% of hours, so we check calibration after the full run.

### `src/evaluate.py`
- **What:** scoring and report plots.
- **How:**
  - **Scores:** RMSE, MAE and R² overall, plus **RMSE and MAE on storm hours only** (because storms are rare, the overall score hides how storms go).
  - **Error by storm level:** MAE and *bias* (does the model guess too low?).
  - **Plots:** predicted-vs-actual hexbins, permutation importance (how much worse the model gets when one clue is shuffled), and the storm case-study plot.

### `src/predict.py`
- **What:** loads the saved model and returns Kp plus its 80% range.
- **How:** the range is widened if needed so it always contains the point estimate, then clipped to 0–9. (The point model and the range models are trained separately, so occasionally the point falls outside the range.)
- Phase 4 adds the live NOAA data path.

### `notebooks/03_modeling.ipynb`
- **What:** runs all of the above in order and saves tables (`reports/metrics/*.csv`) and figures 09–14.
- **How to run:** kernel "Python 3.12 (tormenta)", `FAST = False`, Run All. It takes **~30–60 min**, so close other heavy apps first.
- **Result:** full run took ~20 min on the laptop. Tables are in `reports/metrics/`, figures 09–14 in `reports/figures/`.

### Phase 3 results (full run, 28 Oct 2026)

**Tuned settings (best of the randomised search, CV RMSE in brackets):**

| Model | Best settings | CV RMSE |
|---|---|---|
| Linear Regression | none to tune | 0.673 |
| KNN | 20 neighbours, distance-weighted | 0.709 |
| SVR | C = 4.6, γ = 0.0052, ε = 0.1 | 0.619 |
| Random Forest | depth 12, leaf ≥ 5, 50% of features per split | 0.647 |
| **HistGB** | 700 trees, learning rate 0.039, 31 leaves, leaf ≥ 50, L2 = 0.28 | **0.572** |

**Test set 2020–2026 (each model trained on 1998–2019, tested once):**

| Model | RMSE | MAE | R² | Storm RMSE | Storm MAE |
|---|---|---|---|---|---|
| Persistence (baseline) | 0.862 | 0.643 | 0.57 | 1.37 | 1.06 |
| Linear Regression | 0.671 | 0.505 | 0.74 | 1.49 | 1.02 |
| KNN | 0.674 | 0.513 | 0.73 | 1.41 | 1.19 |
| SVR | 0.609 | 0.461 | 0.78 | 1.10 | 0.84 |
| Random Forest | 0.612 | 0.473 | 0.78 | 1.01 | 0.77 |
| **HistGB** | **0.585** | **0.445** | **0.80** | **0.88** | **0.65** |

**What the results mean:**

| # | Finding | Evidence | Meaning |
|---|---|---|---|
| 1 | **HistGB is best on every metric** | Table above, fig. 10 | Its RMSE is 32% lower than persistence and 36% lower on storms. The production choice is confirmed by the data, not only by convenience. |
| 2 | **Solar wind alone beats "repeat last Kp"** | All 4 ML models beat persistence on overall RMSE | Physics inputs carry real information beyond Kp's own memory. |
| 3 | **HistGB doesn't overfit** | Train 0.548 ≈ CV 0.572 ≈ val 0.530 (fig. 09) | Train and unseen data score alike. Validation is even a bit lower, because 2017–2019 was quiet. |
| 4 | **KNN memorises** | Train RMSE ≈ 0 (its bar is invisible in fig. 09), val 0.633 | Distance weighting means each training point predicts itself perfectly: classic overfitting. |
| 5 | **RF and SVR overfit mildly** | Train–CV gap ~0.07–0.09 | Acceptable, but they generalise worse than HistGB. |
| 6 | **Linear underfits** | Train 0.70: high error everywhere | A straight line can't capture "only southward Bz matters". |
| 7 | **All models under-predict storms** | Bias is negative from Kp 4 upwards (fig. 11). HistGB's is smallest: −0.35 at G1, −0.63 at G3+ | "Regression to the mean": rare extremes get pulled toward common values. Expected and honest. |
| 8 | **Linear *over*-predicts the biggest storms** | G3+ bias +1.16 | A linear model extrapolates extreme Bz × speed without limit, while trees saturate. |
| 9 | **May 2024 storm tracked well** | Fig. 14: predicted ~8.5 vs observed 9, and both storm phases followed | Strong evidence of generalisation, since the model never saw 2020+. |
| 10 | **Small delay at sudden onsets** | Fig. 14: the jump to 7.67 is caught 1–2 h late | A block's Kp covers 3 hours. In its first hour the model hasn't yet seen the solar wind that arrives later in the block. This is an inherent limit of nowcasting. |
| 11 | **Interval nearly calibrated** | The 80% range contains the truth 77.0% of the time on test, 78.3% on the 2025 holdout | Slightly too narrow but close. The fast-mode 69% was an artefact of the tiny search. |
| 12 | **The model relies on physics** | Top features (fig. 13): pressure, 3 h Newell coupling, speed, \|B\|, 6 h Newell, then hour-of-day and season | Matches theory: energy coupling (Newell) and compression (pressure). Time features matter because of Earth's tilt (Russell–McPherron) and Kp's station network. |
| 13 | **Storm weighting is a trade-off** | Weighted HistGB: storm RMSE 0.876 → 0.839 (−4%) but overall 0.585 → 0.599 (+2.5%) | Weighting helps storms a little and costs a little everywhere else. Production stays **unweighted** (better overall, and the weekly check uses overall RMSE). |

**Production model** (`models/tormenta_v20261028.joblib`, 3.4 MB):
- Trained on 1998 → 2025-07-10.
- On the held-back 6 months (Jul 2025 – Jan 2026): RMSE 0.581, R² 0.82, storm RMSE 0.70, 80%-range coverage 78%.
- These numbers are the baseline the weekly retrain must match to replace it.

---

## Phase 3b — Improvement round (v1 → v2)

**Why:** v1's error was clearly highest in the **first hour of each 3-hour Kp block** (validation RMSE 0.56 vs 0.51; on storms 1.02 vs 0.79). The model didn't know where it was inside the block, or what had already happened in it.

### What changed (all in `src/features.py`, 56 → 66 features)

| New feature(s) | Plain meaning | Leakage-safe because… |
|---|---|---|
| `block_hour` (0/1/2) | "Which hour of the 3-hour block are we in?" | Just the clock |
| `newell_block_mean`, `newell_block_max`, `vbs_block_mean`, `bz_block_min` | "What has the solar wind done so far in this block?" | Uses only hours from the block start up to now. A test proves that changing a *later* hour of the block doesn't change earlier features. |
| `pressure_mean3h`, `pressure_max3h`, `pressure_change1h` | Recent pressure, and sudden jumps (a CME/shock arriving) | Trailing windows only |
| `newell_mean12h`, `newell_mean24h` | Longer memory of energy input | Trailing windows only |

Also new in `src/train.py`:
- **Wider HistGB search:** 20 tries instead of 8.
- **Ensemble:** a plain average of HistGB + RF + SVR. Nothing is fitted, so nothing can leak.
- **Fair gate:** the new model replaces the current one only if it is at least as good on the same held-back 6 months, scored in the same run. The code also *checks* that neither model was trained on those months.

### How we avoid fooling ourselves
1. Tuning uses cross-validation inside 1998–2016 only.
2. The decision to keep v2 is made on **CV + validation only**. The rule was fixed in advance: keep v2 only if both get better.
3. The test set (2020+) is used **once more** at the end, and **both v1 and v2** test results are reported (v1 is archived in `reports/v1/`).
4. 3 new automatic tests (7 total, all pass):
   - block-so-far features ignore later hours of the block;
   - the past-Kp comparison never sees the current block;
   - production features never include Kp.

### Ablation: "what if we were allowed to use past Kp?"
- **What:** HistGB with 3 extra inputs: Kp of the two previous *finished* blocks and the average of the last 24 h.
- **Why:** to show how much our "no geomagnetic inputs" rule costs. It is **not** used in production.

### Notebooks
- `04_improvements.ipynb` (~15–20 min): v1 vs v2 on CV + validation, error by block hour, the decision, and the past-Kp comparison.
- Then re-run `03_modeling.ipynb` (~30–40 min): all models with v2 features, the single test evaluation, the gate against v1, and promotion if v2 is better.

**Result of `04_improvements.ipynb` (2026-10-29), validation 2017–2019, no test data used:**

| HistGB | CV RMSE | val RMSE | val MAE | val R² | storm RMSE | storm MAE |
|---|---|---|---|---|---|---|
| v1 (56 features) | 0.572 | 0.529 | 0.409 | 0.809 | 0.889 | 0.710 |
| v2 (66 features) | **0.561** | **0.522** | **0.404** | **0.814** | **0.853** | **0.674** |

Validation RMSE by position inside the 3-h block:

| | hour 1 | hour 2 | hour 3 |
|---|---|---|---|
| v1 all | 0.564 | 0.508 | 0.514 |
| v2 all | 0.556 | 0.508 | 0.500 |
| v1 storm | 1.020 | 0.843 | 0.789 |
| v2 storm | **0.982** | 0.819 | **0.740** |

- **Decision:** CV improves ✅, validation improves ✅ → **adopt v2** (rule fixed in advance).
- The overall gain is small (−0.011 CV, −0.007 val), but **storm RMSE drops by 4%** (0.889 → 0.853). Storms are the cases that matter most for warnings.
- Hour 1 of a block got better, as intended, but it is still the hardest hour: the solar wind that drives the rest of the block hasn't arrived yet.
- Best v2 settings: learning rate 0.039, 700 trees, 31 leaves, min 50 samples per leaf, L2 0.28.
- **Past-Kp ablation (validation, not production):** adding Kp from previous blocks only improves RMSE from 0.522 to 0.512 (storm 0.853 → 0.832). **Our solar-wind-only model is within 0.01 of a model that cheats with past Kp**, so excluding geomagnetic inputs costs us almost nothing. Persistence scores 0.819 here.

**Result of the `03_modeling.ipynb` re-run with v2 features (2026-10-29), test 2020 → 2026-01, evaluated once:**

| Model | v1 RMSE | v2 RMSE | v1 storm RMSE | v2 storm RMSE | v2 R² |
|---|---|---|---|---|---|
| Persistence | 0.862 | 0.862 | 1.368 | 1.368 | 0.566 |
| Linear Regression | 0.671 | 0.665 | 1.489 | 1.470 | 0.742 |
| KNN | 0.674 | 0.657 | 1.408 | 1.337 | 0.748 |
| SVR | 0.609 | 0.605 | 1.101 | 1.079 | 0.786 |
| Random Forest | 0.612 | 0.606 | 1.006 | 0.972 | 0.785 |
| **HistGB** | 0.585 | **0.573** | 0.876 | **0.846** | 0.808 |
| Ensemble (HistGB+RF+SVR) | – | 0.571 | – | 0.910 | 0.809 |

- **Every model improved**, so the gain comes from the new features, not tuning luck. CV even picked the same HistGB settings as for v1.
- **HistGB:** RMSE −2%, storm RMSE −3.4%, MAE 0.445 → 0.437. It is 34% better than persistence overall and 38% better on storms.
- **The ensemble** is a hair better overall (0.571) but much worse on storms (0.910), because SVR and RF under-predict big storms. HistGB stays the production model.
- **Storm under-prediction** shrank (G3+ bias −0.63 → −0.57) but is still the main limitation.
- **Weighting ablation (v2):** storm RMSE 0.829 vs 0.846, overall 0.584 vs 0.573. Same trade-off as v1, so production stays unweighted.
- **Block hour (test, HistGB):** 0.614 / 0.559 / 0.543. Hour 1 is still the hardest.
- **Feature importance:** the new `newell_block_max` is now #1 by far, and the new `pressure_max3h` is #2. The model now uses "the strongest coupling so far in this block", which matches how Kp is defined (the biggest disturbance in the 3 h).
- **May 2024 storm:** predicted peak 8.6 vs observed 9. **80% interval coverage on test is 75.7%** (v1: 77.0%): slightly narrow. This number was recomputed separately because that notebook cell's printout wasn't saved.

**Gate (same 6-month holdout, both scored in this run, neither trained on it):**

| | RMSE | storm RMSE | coverage |
|---|---|---|---|
| v1 (incumbent) | 0.581 | 0.702 | 78.3% |
| v2 (candidate) | **0.580** | **0.695** | 77.4% |

0.580 ≤ 1.02 × 0.581, so **v2 was promoted**: `models/tormenta_v20261029_1003.joblib` → `models/current.joblib`. v1 is kept for rollback. The two are nearly tied on this holdout because late 2025 had few big storms, and v2's edge is mainly on storms.

**Figures:** `reports/figures/09–14` are now v2. The v1 versions are in `reports/v1/figures/`, and the tex Phase 3 section points there. The v2 versions are archived in `reports/v2/` before the v3 run.

## Phase 3c — Final round (v2 → v3): underfitting check, physics ideas, interval calibration

**Why:** after v2 we asked "is the model underfitting, and can it generalise better?" The train / CV / val / test RMSEs (0.534 / 0.561 / 0.522 / 0.573) are close together, so it is not overfitting. Earlier searches over bigger trees didn't improve CV, which suggests the limit is the *information in the inputs*, not model size. This round tests that directly and tries the remaining leakage-safe ideas. **It is the last modelling round**: afterwards the model is frozen, so the test set isn't reused again.

### What was added (code)
| Change | File | What / why |
|---|---|---|
| **Storm memory** (4 features) | `features.storm_memory` | `newell_decay6h/24h`, `vbs_decay6h/24h`: a decaying average of energy input (weights halve every 6 h or 24 h), a rough "charge level" of Earth's magnetic field. Storms build up and recover slowly; plain windows only capture that coarsely. |
| Fixed 48 h window | same | Pandas `ewm` would use *all* history, but the live app only has ~3 days of SWPC data, which would cause train/serve skew. So the decay is computed over exactly the last 48 h in both paths. `MIN_HISTORY_HOURS` was raised from 24 to 48. |
| **Monotonic constraints** | `config.MONOTONIC_*`, `features.monotonic_cst`, `train._constrain` | Tells HistGB that Kp may only go **up** as speed, V·Bs or Newell coupling go up, and only **up** as Bz goes more negative. This is physics knowledge, so storms bigger than most of the training data behave sensibly. |
| **Conformal interval (CQR)** | `train.conformal_margin`, `predict.py` | Measures how far observed Kp falls outside the q10–q90 band on data the quantile models **did not train on** (out-of-fold CV years 2007–2016 + validation 2017–2019). One margin is then added to both sides so coverage is 80% there. It is stored in the model bundle as `interval_margin`; v1/v2 bundles default to 0. |
| **Learning + complexity curves** | `train.learning_curve`, `train.complexity_curve`, `evaluate.plot_diagnostic_curves` | They show whether more data or bigger trees would help: the textbook underfitting test. |
| Flags | `config.USE_MEMORY_FEATURES`, `config.USE_MONOTONIC` | Set according to 05's decision. **Both are now `False`** (rejected). The code stays, so the report can show what was tried. |
| 2 new tests (9 total) | `tests/test_features.py` | Storm memory ignores data older than its 48 h window; the monotonic constraint names are real feature columns. |

### Leakage protocol
1. All comparisons use the **fixed v2 HistGB settings**, `TimeSeriesSplit(5)` CV inside 1998–2016, and validation 2017–2019. **No test, no gate holdout.**
2. Rule fixed in advance, step by step: storm memory vs v2, then monotonic on top of the winner. Each is adopted only if **both** CV and val RMSE improve.
3. The conformal margin uses only predictions on unseen data from the training/validation years (never test, never the gate holdout). It is applied in 03 regardless of the outcome, because it is a calibration rather than a model change.
4. Test is then used **once** in 03, with v1 → v2 → v3 shown side by side. v2 is archived in `reports/v2/`.

### Notebooks
- `05_final_round.ipynb` (~20–25 min): learning/complexity curves (figure 15), the variants table, the conformal check, and the decision. It also says whether `src/config.py` matches the decision.
- Then re-run `03_modeling.ipynb` (~35–45 min). It now adds a conformal step, a v1/v2/v3 test table, raw vs conformal coverage, and complete feature groups.

Both notebooks were smoke-tested in fast mode without errors. In fast mode the conformal step took test coverage from 69% to 80.5%.

**Result of `05_final_round.ipynb` (2026-10-30), CV + validation only.** The browser stopped updating mid-run, but every cell finished and saved its CSV/figure, so the numbers below come from `reports/metrics/*.csv`.

**1. Not underfitting** (figure `15_learning_complexity.png`):

| max leaves per tree | 7 | 15 | **31** | 63 | 127 | 255 |
|---|---|---|---|---|---|---|
| train RMSE | 0.591 | 0.565 | 0.534 | 0.490 | 0.427 | 0.339 |
| val RMSE | 0.535 | 0.527 | **0.522** | 0.521 | 0.522 | 0.523 |

- Bigger trees keep lowering *train* error, but *validation* error is flat from 31 leaves on and starts rising at 255 (overfitting). So the model is complex enough.
- Learning curve: val RMSE goes 0.578 (5k hours) → 0.537 (42k) → 0.525 (83k) → 0.522 (167k). Doubling the data at the end gains only 0.003, so more data of the same kind won't help much.
- **Conclusion:** the remaining error is an *information limit*. The solar wind measured at one point (L1) can't fully determine a ground-based index, so it isn't a modelling flaw.

**2. Variants** (fixed v2 settings):

| | CV RMSE | val RMSE | storm RMSE | decision |
|---|---|---|---|---|
| A: v2 | 0.5609 | 0.5219 | 0.853 | baseline |
| B: + storm memory | 0.5594 ✅ | 0.5229 ❌ | 0.854 | **rejected** (CV better, val worse) |
| C: v2 + monotonic | 0.5659 ❌ | 0.5275 ❌ | 0.859 | **rejected** |

- **Storm memory** adds nothing beyond the 12/24 h Newell means and block-so-far features v2 already has.
- **Monotonic constraints** cost accuracy: once other features are fixed, Kp isn't strictly monotonic in each input (e.g. correlated features share the effect). Physics-plausible, but the data says no.
- Both stay switched off. The model's features are identical to v2's (66 columns).

**3. Conformal calibration works:**

| calibration block (unseen by the model) | raw coverage | calibrated coverage |
|---|---|---|
| 2004-05 → 2007-07 | 70.4% | 76.1% |
| 2007-07 → 2010-09 | 74.9% | 81.8% |
| 2010-09 → 2013-11 | 73.4% | 79.6% |
| 2013-11 → 2016-12 | 75.2% | 80.7% |
| 2017 → 2019 (validation) | 76.0% | 81.9% |

The raw band is consistently too narrow (70–76%). One margin brings every period close to 80%, and it is applied in 03.

**Result of the final `03_modeling.ipynb` run (2026-10-30):**
- Features (66) and tuned settings are identical to v2, so **point predictions and test metrics are exactly v2's**: HistGB test RMSE 0.573, MAE 0.437, R² 0.808, storm RMSE 0.846. Every model's test numbers matched v2 to the last digit, a good reproducibility check.
- **Conformal margin = +0.062 Kp** on each side of the band.

| 80% interval | raw (v2) | conformal (v3) |
|---|---|---|
| test 2020 → 2026-01 coverage | 75.7% | **80.8%** |
| gate holdout (last 6 months) coverage | 77.4% | **82.0%** |
| mean width on test | 1.29 Kp | 1.41 Kp |

  The band is now honest: it contains the truth about 80% of the time, at the cost of being 0.12 Kp wider.
- **Gate:** same RMSE as v2 (0.580 vs 0.580 ≤ 1.02×), so **v3 promoted**: `models/tormenta_v20261030_0737.joblib` → `current.joblib`. v1 and v2 are kept for rollback.
- The browser lost its connection again mid-run, so the saved notebook is missing the printed tables for sections 2–5. All results are in `reports/metrics/*.csv` and `reports/figures/`.

### 🧊 Model frozen
No more modelling rounds. The test set has been used once per version (v1, v2, v3), and further tuning against it would make it less trustworthy. Next is Phase 4 (live nowcast).

---

## Phase 4 — Live nowcast

**Goal:** predict Kp *right now* from NOAA's real-time data, using exactly the same feature code and model as training.

### Surprise: the planned live feeds no longer exist
We checked every endpoint before writing code. SWPC has **retired** the `products/solar-wind/mag-3-day.json` and `plasma-3-day.json` feeds in the plan (404), and the new `json/rtsw/` feeds only keep 24 hours. We found a better replacement:

**`products/geospace/propagated-solar-wind.json`**
- **7 days** of 1-minute IMF + plasma from whichever L1 spacecraft is active (now "SOLAR1"; ACE and IMAP are backups).
- **Already time-shifted to Earth** (delay 50–75 min), just like OMNI. This *fixes* the "propagation offset" problem in the original plan: live and training timing now match.
- Checked: Bx/By/Bz are **GSM** (identical to RTSW's `*_gsm` columns), and `bt` is the field magnitude, like OMNI's scalar B.

Also checked:
- **F10.7:** SWPC's 30-day feed matches GFZ's observed F10.7 within 0.5 (rounding), so it's the same measurement.
- **NOAA Kp feed:** its format has changed (now a list of `{time_tag, Kp, …}`); the parser handles the new format.

### Files
| File | What it does | Why |
|---|---|---|
| `src/ingest/fetch_live.py` | Downloads the feeds, renames SWPC fields to our training column names, averages 1-min data into **OMNI-style hours** (hour HH = mean of HH:00–HH:59). An hour needs ≥ 20 minutes of data per column, else NaN. Merges F10.7: GFZ history file first, SWPC only for newer days. Also parses NOAA estimated Kp and GFZ quick-look Kp. | The live data must look exactly like training data before it reaches `features.py`. |
| `src/predict.py` → `predict_hourly`, `nowcast()` | Builds features with the **same** `build_features`, drops the first 48 h (warm-up for trailing windows), skips hours with no current Bz/speed, predicts Kp + 80% range, and flags `ahead` hours. | One code path for everything; no train/serve skew. |
| `src/evaluate.py` → `attach_block_kp`, `plot_live` | Matches each hour to its 3-h Kp block; plots the nowcast vs GFZ and NOAA Kp. | Live sanity check. |
| `tests/test_live.py` (5 tests, 14 total) | **Parity test:** fake SWPC 1-min data built from an hourly frame goes through the live path and gives *identical* features to the training path. Also: partial hours → NaN, F10.7 merge order, feed formats. | Proves no train/serve skew. |
| `notebooks/06_live_nowcast.ipynb` | Live snapshot: inputs, Kp now, comparison table, figure 16. | Demo + report evidence. |

### Why "ahead"?
The spacecraft sits ~1.5 million km upstream, so the solar wind it measures reaches Earth about an hour later. The newest propagated hour is therefore slightly **in the future**: a free ~1 h forecast, which we label separately from the nowcast.

### What we got (snapshot 2026-10-30, 25–30 Oct, quiet conditions)
| compared with | hours | RMSE | MAE | bias | 80% coverage |
|---|---|---|---|---|---|
| **GFZ quick-look Kp** (our label source) | 121 | **0.59** | 0.41 | −0.25 | **88%** |
| NOAA estimated Kp | 118 | 0.70 | 0.56 | −0.47 | 75% |

- Against GFZ, the live error (0.59) is about the same as our test error (0.573). **The model works on real-time data as well as on the archive**, which is the main evidence that there's no train/serve skew.
- NOAA's estimate runs ~0.2 higher than GFZ this week (they use different station sets and methods), which explains most of the worse NOAA numbers.
- A slight under-prediction in very quiet hours (e.g. 30 Oct: slow wind ~315 km/s, density ~2): Kp ~1.5 observed vs ~0.3 predicted. Five quiet days is a small sample, so it's a sanity check, not a new test score.
- Figure `16_live_nowcast.png`. Numbers are in `reports/metrics/live_snapshot.csv`; each run gives a new snapshot.

**Next:** Phase 5, the three deployments (Streamlit, Hugging Face Space, Flask), all calling `nowcast()`.

---

## Phase 5 — Deployments

### 5a. Flask app (localhost) ✅
**Run:** from the project folder, `.venv\Scripts\python app\flask_app\app.py`, then open http://127.0.0.1:5000.

| Route | What it does |
|---|---|
| `GET /` | Web page with a form for the 8 inputs (|B|, Bx, By, Bz, speed, density, temperature, F10.7) and a **"Use live data"** button |
| `POST /` | Form submit → Kp, 80% range and storm level, or the form again with a red message under each bad field |
| `GET /live` | Live nowcast from NOAA (Kp now, next hour, last 24 h table), and **fills the form with the latest live values** so you can tweak them |
| `POST /predict` | JSON API: send the 8 fields, get `kp_pred`, `kp_lo`, `kp_hi`, `level`. Bad input → HTTP 400 with an error per field and the allowed ranges |
| `GET /api/live` | JSON live nowcast; HTTP 503 with a clear message if NOAA is unreachable |
| `GET /health` | Model version and training cutoff |

**Manual input, and why "steady for 3 days":** the model also uses lags (1–9 h ago) and 6–24 h averages, which a single set of numbers can't supply. `predict.predict_steady` repeats the entered values for the past 3 days, i.e. it answers *"what Kp would these conditions give if they had been steady?"*, and still runs the shared `build_features`. The page says this explicitly. Example: quiet inputs → Kp 0.6; |B| 40, Bz −35, 800 km/s → Kp 8.2.

**Validation** (`predict.validate_inputs`, shared by all apps):
- Every field must be present and numeric.
- Each value must fall within physical limits, e.g. speed 200–3000 km/s and density 0.01–200 cm⁻³.
- |B| can't be smaller than the size of its own components.

**Other details:**
- Live results are cached for 5 minutes (NOAA updates every minute; no need to download on every click).
- Works in light and dark mode.
- `tests/test_flask_app.py` has 9 tests with the network mocked: valid/invalid JSON, a per-field error message, the |B| consistency check, a non-object JSON body, HTML error display, the NOAA-offline case (503), and the live JSON shape. **23 tests total, all passing.**
- `flask==3.1.3` is pinned in `requirements.txt`.

### 5b. Code on GitHub ✅
Public repo: **https://github.com/Syeda-Aliza-Ayaz/Tormenta** (uploaded 2026-11-06). Raw/processed data stay gitignored. Models (~3.5 MB each) and `data/f107_history.csv` are committed because the apps need them.

### 5c. Streamlit dashboard: `app/streamlit_app.py` ✅ live at https://tormenta.streamlit.app/
**Run locally:** `.venv\Scripts\streamlit run app\streamlit_app.py`

**Three tabs:**
- **Live nowcast:** Kp now (+ storm level), next hour if available, and current solar wind; the figure-16-style chart vs GFZ and NOAA Kp; live accuracy vs GFZ quick-look Kp; and the hourly table.
- **Try your own inputs:** 8 number boxes with physical min/max, a "Fill with the latest live values" button, and Predict. Validation errors are shown in red (e.g. "|B| (5 nT) cannot be smaller than the size of its components (20.1 nT)").
- **About the model:** test metrics, inputs, limitations and data credits.

**Other details:**
- Live data is cached for 5 minutes, and there's a Refresh button.
- If NOAA doesn't answer, the app shows a friendly error instead of crashing. This happened once during testing on our slow connection, and the message appeared correctly.
- **Tested** with Streamlit's `AppTest` on live data:
  - no exceptions;
  - Kp now 1.5 at 323 km/s;
  - the fill button works;
  - Bz −20 and 700 km/s with |B| 5 is rejected with the message above;
  - with |B| 22, the prediction is **Kp 7.3 (G3+)**.

### 5d. Hugging Face ✅ (free model repo + static Space; Gradio runs locally)
**What happened:** creating a Gradio Space failed with **402 Payment Required**. Hugging Face now only hosts Gradio/Docker Spaces for PRO subscribers (~$9/month); static Spaces and model repos are still free. We chose the free route:

| Published | URL | What's there |
|---|---|---|
| **Model repo** | https://huggingface.co/aliza-ayaz/tormenta | Model card (`app/hf_space/model_card.md` → `README.md`): task, model, inputs, training/selection, test results vs persistence, intended use, limitations, **copy-paste usage code**, licences. Plus `models/current.joblib`, `src/**`, `data/f107_history.csv` and pinned `requirements.txt`, so the model is usable straight from HF. |
| **Static Space** | https://huggingface.co/spaces/aliza-ayaz/tormenta | Landing page (`app/hf_space/space/index.html`): headline results, the May 2024 storm figure, model comparison, error-by-level figure, live-check figure, limitations, and buttons to the live Streamlit app, the model repo and GitHub. |
| **Gradio app** | local: `.venv\Scripts\python app\hf_space\app.py` → http://127.0.0.1:7860 | Live tab + manual tab with 3 examples; useful for the viva demo. |

- `sync_hf.py --user aliza-ayaz` publishes both repos in one go. Phase 6's weekly retrain will call it to push the new model.
- **Verified:** downloading the model repo fresh into an empty folder and running the model card's code works end to end (live Kp 1.46; the manual storm example gives Kp 7.0). The Space status is RUNNING.
- `tests/test_hf_space.py` checks that the model repo has every file the code needs and that every image the page uses gets uploaded (25 tests total).

**For the report/viva:** "HF Gradio hosting became paid, so we published the model + model card on the HF Hub (the standard way to share ML models) and a static Space as the project page; the live interactive app runs on Streamlit Cloud."

**Versions:** `streamlit==1.67.0` is in `requirements.txt` (Streamlit Cloud installs it). `gradio==6.31.0` and `huggingface_hub==2.4.0` are in `requirements-dev.txt`, so Streamlit Cloud doesn't download Gradio.


---

## Phase 6 — Weekly automatic retraining (the "slow loop")

**Goal:** keep the model fresh without anyone touching it. Every Monday 03:00 UTC (08:00 PKT), GitHub Actions downloads the newest data, retrains, and replaces the live model **only if it is at least as good**.

### Files
| File | What it does | Why |
|---|---|---|
| `src/ingest/fetch_omni.py` → `parse_spdf`, `load_omni_spdf` | Reads NASA's yearly files `omni2_YYYY.dat` (55 numbers per line) and returns **exactly the same columns** as our original `.lst` parser. Both parsers now share one cleaning function. | GitHub's servers don't have our 24 MB OMNIWeb file, so they rebuild 1998 → now from the yearly files. |
| `src/preprocessing.py` (`build_hourly`) | Now stops at the **last hour that has any solar-wind data**. | The current-year file has empty "fill" rows up to 31 December. Without this, GFZ labels for those hours would enter training with empty features. |
| `src/update.py` | 1) download GFZ + 29 yearly OMNI files; 2) rebuild the hourly table **from scratch**; 3) refresh `data/f107_history.csv`; 4) if there's new definitive data, retrain the **frozen** configuration up to the start of the gate holdout; 5) gate; 6) save + log. `--dry-run` stops after the gate decision. | One script for the whole slow loop. |
| `src/train.py` (`save_bundle`) | New options: `keep_rejected=False` logs a rejected candidate in `metrics_history.json` without saving its 3.5 MB file; `note` explains the entry. | Keeps the repo from filling up with unused models. |
| `.github/workflows/retrain.yml` | Weekly schedule + a manual "Run workflow" button with a **dry run** option. Steps: install the exact pins → run all tests → `update.py` → commit `models/` + `data/f107_history.csv` → `sync_hf.py` (uses the `HF_TOKEN` secret). | Automation; Streamlit Cloud redeploys automatically after the push. |
| Tests | `test_omni_spdf.py`: the SPDF parser vs a 3-day sample cut from our `.lst` (offline), the same vs NASA's real 2024 file (online), and trailing fill hours being dropped. `test_update.py`: "no new data → no retrain", and the workflow output format. **30 tests total.** | |

### Rules the weekly retrain follows (no leakage, no cheating)
- **No re-tuning, no new features:** it retrains the frozen v3 configuration (same 66 features, HistGB settings and conformal margin). `update.py` stops with an error if the feature list ever differs from the live model's.
- **The test set is not re-scored.** The new model trains on 2020+ too, so the only fair check is the gate holdout.
- **The gate:**
  - the holdout is the last 6 months of definitive Kp;
  - the candidate is trained only up to the holdout start;
  - both models are scored on it in the same run;
  - the code asserts the current model never saw it.
- **If there's no new definitive data,** the script stops ("nothing to do"), so no pointless new versions.

### NASA's server is blocked from our network
`spdf.gsfc.nasa.gov` times out from here (OMNIWeb too), but works from GitHub (US). So the parser was checked two ways:
- offline, against a sample of our original training file;
- online, inside GitHub Actions, against NASA's real 2024 file.

That online test passed.

### Dry run on GitHub (2026-11-06, 2.5 minutes, nothing saved)
```
28 passed, 2 skipped (the 2 local-data tests)
OMNI 1998-01-01 → 2026-12-31 (file) | hourly table ends 2026-10-26 01:00   ← trailing fill rows dropped ✓
definitive labels with features end 2026-06-30 | gate holdout starts 2025-12-30
current model tormenta_v20261030_0737 trained until 2025-07-10
candidate gate RMSE 0.5794 vs current 0.5791 (tolerance ×1.02) → promote: True
```
**What this tells us:**
- **New data arrived:** OMNI now reaches 26 Oct 2026, and GFZ definitive Kp reaches 30 Jun 2026. The holdout moved forward 6 months, to Jan–Jun 2026.
- **The current model holds up on data it has never seen:** RMSE 0.579 on the first half of 2026, the same as on its own holdout (0.580) and the test set (0.573). **No sign of drift.**
- **The candidate is equally good (0.5794 vs 0.5791)** and within the 2% tolerance, so a real run would promote it. It's trained on 6 more months of data.

**Next real run:** Monday's schedule, or "Run workflow" with dry run unticked. It will commit the new model (v4) and publish it to Hugging Face.
