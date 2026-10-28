# Tormenta — Project Notes

**Team:** Aliza, HRK · **Course:** CT-378 Machine Learning, NED University (Fall 2026)

A running, plain-language log of every file in the project: **what** it does, **how**, **why**, and **what we got from it**. Updated as each phase is built. The detailed, report-ready version (data sources, variable glossary, physics, viva notes) is [`report_notes.tex`](report_notes.tex).

**Status:** Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅ · Phase 3–7 ⬜

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
