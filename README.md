# Tormenta: geomagnetic activity forecast and nowcast

Tormenta forecasts geomagnetic activity **for the next 7 days** (daily Ap and daily max Kp, with 80% ranges and a
storm warning) and **nowcasts the current Kp index** (0–9) from solar-wind measurements taken about an hour upstream
of Earth. Forecasts are issued every morning and scored against official GFZ data as it arrives.
CT-378 Machine Learning, NED University, Fall 2026 · **Alizeh & HRK**.

| | |
|---|---|
| **Live app (Streamlit)** | <https://tormenta.streamlit.app/>: 7-day forecast, "Try the forecaster", scorecard, live nowcast, what-if |
| **Model + model card (Hugging Face)** | <https://huggingface.co/aliza-ayaz/tormenta> |
| **Live Space (Hugging Face)** | <https://huggingface.co/spaces/aliza-ayaz/tormenta> (the Streamlit app running in your browser; first load ~1 min) |
| **Flask app** | runs locally (see below): `/forecast`, `/api/forecast`, nowcast form and API |

## 7-day forecaster

### Results (test period 2020-01-01 → 2026-06-30: 2,379 issue days, 325 storm days, scored once)

| Daily Ap, RMSE | day 1 | day 3 | day 7 | skill vs 27-day average (days 1–7) |
|---|---|---|---|---|
| **HistGB (headline)** | **10.79** | **11.91** | **12.00** | **+0.100** |
| NOAA SWPC official forecast | 10.89 | 11.90 | – | +0.134 (days 1–3 only) |
| ARIMAX | 10.96 | 12.15 | 12.17 | +0.069 |
| ARIMA | 10.97 | 12.20 | 12.22 | +0.062 |
| SARIMA (27-day season) | 11.11 | 12.43 | 12.49 | +0.025 |
| Chronos-Bolt (pretrained transformer, zero-shot) | 11.83 | 12.66 | 12.65 | −0.015 |
| 27-day average (reference) | 12.27 | 12.45 | 12.48 | 0 |

- **HistGB is the best of the project's models at every lead day** and level with NOAA's official forecast on days
  1–3 (ahead on day 1, behind on day 2, tied on day 3).
- **80% ranges** contain the observed value on 80–82% of days at every lead day.
- **Storm warning** (separate classifier, thresholds tuned for rare events): Heidke skill 0.20–0.30 at every lead
  day, catching 29–54% of storm days. The value forecasts alone catch almost none after day 1.
- **Limit:** storms caused by sudden solar eruptions (e.g. May 2024) cannot be foreseen from past values alone.
- Model choice used validation 2017–2019 only, by a rule fixed in advance; ARIMA, SARIMA and Chronos did not pass it
  and are not issued live. Per-day storm tables: [`reports/forecast/storm_tables.md`](reports/forecast/storm_tables.md).
  Figures: [`reports/forecast/figures/`](reports/forecast/figures/).

### How it works

```
GFZ daily Kp/Ap/F10.7 (1932→) ─► src/daily.py ─► src/forecast/features.py (causal: lags, 27/54/81-day recurrence,
                                                   F10.7, season)
   train 1947-06 → 2016 · validation 2017–2019 · test 2020 → 2026-06 (once) · live models refit on 1947–2019
   ├─► HistGB (14 direct models) · ARIMAX · storm classifier (7) · 80% ranges   ─► models/forecast/
   └─► daily GitHub Actions job (src/issue.py) ─► forecasts/log.csv (append-only) + storm_log.csv + scores
                                                ─► Streamlit · Flask · HF Space · weekly health check
NOAA SWPC forecasts (archive + daily copies) ─► benchmark only, never an input
```

- **Daily job** (`.github/workflows/daily.yml`, several overnight UTC slots): issues D+1 … D+7 from yesterday's GFZ
  data, saves NOAA's forecasts, scores every forecast whose day has arrived, commits `forecasts/`, publishes to
  Hugging Face. Forecasts are never edited and never backfilled.
- **Retraining only when performance drops** (`src/forecast/monitor.py`, weekly): HistGB's 56-day skill against the
  27-day average on live scores; a retrain happens only after two degraded checks in a row, and the new model must
  beat the current one on the newest 6 months of data.

## Nowcaster

### Results (test years 2020 → Jan 2026, never used for training or model selection)

| Model | RMSE | R² | RMSE on storm hours (Kp ≥ 5−) |
|---|---|---|---|
| Persistence (previous Kp) | 0.862 | 0.566 | 1.368 |
| Linear Regression | 0.665 | 0.742 | 1.470 |
| KNN | 0.657 | 0.748 | 1.337 |
| SVR | 0.605 | 0.786 | 1.079 |
| Random Forest | 0.606 | 0.785 | 0.972 |
| **HistGradientBoosting (production)** | **0.573** | **0.808** | **0.846** |

- **Interval:** the 80% interval contains the observed Kp in 80.8% of test hours.
- **Live:** RMSE against GFZ quick-look Kp is 0.59.

### How it works

```
NASA OMNI2 hourly (1998→) ─┐                         ┌─► weekly health check ─► retrain only if degraded ─► gate ─► models/current.joblib
GFZ definitive Kp (labels) ┴─► hourly table ─► src/features.py (shared) ─► HistGB + quantile models + conformal margin
NOAA SWPC real-time feeds ──► hourly means ──────────┘                      └─► Streamlit · Flask · Gradio · HF model repo
```

- **Inputs:** IMF |B|, Bx, By, Bz (GSM), proton speed, density, temperature, and F10.7 flux. **No geomagnetic
  indices** are used as inputs.
- **Features:** 66 causal (trailing-only) features: coupling functions, pressure, lags, 3–24 h statistics,
  position inside the 3-h Kp block, and time of day and year. One shared `src/features.py` is used for training
  and live serving, and a parity test checks they match.
- **Model selection:** time-ordered splits (train 1998–2016, validation 2017–2019, test 2020+) with
  `TimeSeriesSplit` CV. Every improvement was decided on CV + validation by a rule fixed in advance.

## Repository layout

```
src/              config, ingest (OMNI, GFZ, live SWPC, NOAA forecasts), preprocessing, features, train, evaluate,
                  predict, update (nowcaster retrain), daily.py, backtest.py, scorecard.py, issue.py (daily job)
src/forecast/     features, baselines, gbm (HistGB), arima, chronos_model, intervals, storm, monitor, test_eval,
                  figures, tables, app_data, registry
notebooks/        01 preprocessing · 02 EDA · 03 modelling · 04 v1→v2 · 05 final round · 06 live nowcast
app/              streamlit_app.py · flask_app/ · hf_space/ (model card, in-browser Space page, sync_hf.py, Gradio app)
models/           current.joblib (nowcaster) + versions + metrics_history.json · forecast/ (forecaster models)
forecasts/        live forecast log (append-only), storm log, scores, NOAA copies, monitor state, app data
reports/          nowcaster figures/ and metrics/ (v1, v2 archives) · forecast/ (metrics, figures, storm tables)
tests/            leakage, live parity, parsers, every forecaster's causality, daily job, monitor, apps
docs/             PROJECT_NOTES.md (what/why per file) · report_notes.tex (report + viva material)
PLAN.md, DECISIONS.md   forecaster plan and decision log (every decision, why, and its result)
.github/workflows/      daily.yml (forecast) · retrain.yml (weekly health checks and retraining)
```

## Setup (Windows, Python 3.12)

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m ipykernel install --user --name tormenta --display-name "Python 3.12 (tormenta)"
```

Use Python **3.12** and the exact pins: models are pickled scikit-learn 1.9.1 objects, and the code warns if the
version differs. The Chronos comparison is optional:
`pip install -r requirements-chronos.txt -c requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu`.

**Data** (`data/raw/`, not in git):
- The OMNIWeb subset `omni2_*.lst` + `.fmt` (1998-01-01 onward) for the nowcaster.
- The GFZ file `Kp_ap_Ap_SN_F107_since_1932.txt` from <https://kp.gfz.de> (`python -m src.daily` downloads it).

Alternatively, `python -m src.update --dry-run` downloads everything from NASA SPDF and GFZ and rebuilds
`data/processed/` (needs access to spdf.gsfc.nasa.gov).

## Run

**Forecaster**
```bat
python -m src.daily                          &:: download GFZ, build the daily table
python -m src.backtest                       &:: validation scorecard (all models + NOAA)
python -m src.backtest --period recent       &:: the live models on the newest provisional days
python -m src.forecast.gbm --reuse-params    &:: retrain HistGB with the tuned settings, apply its rule
python -m src.forecast.arima --reuse-settings
python -m src.forecast.storm                 &:: storm classifier and its thresholds
python -m src.forecast.intervals             &:: 80% ranges
python -m src.issue                          &:: what the daily job runs
python -m src.forecast.monitor               &:: weekly health check (add --act to allow a retrain)
python -m src.forecast.figures ; python -m src.forecast.tables
```
`python -m src.forecast.test_eval` scored the test period once; it refuses to run again without `--force`.

**Notebooks** (nowcaster record; kernel "Python 3.12 (tormenta)", **Kernel → Restart & Run All**, in order):
`01_preprocessing` (~1 min) · `02_eda` (~2 min) · `03_modeling` (~40 min) · `04_improvements` (~20 min) ·
`05_final_round` (~40 min) · `06_live_nowcast` (~1 min, needs internet).

**Tests**
```bat
.venv\Scripts\python -m pytest -q
```

**Apps**
```bat
.venv\Scripts\streamlit run app\streamlit_app.py      &:: dashboard   → http://localhost:8501
.venv\Scripts\python app\flask_app\app.py             &:: Flask + API → http://127.0.0.1:5000
.venv\Scripts\python app\hf_space\app.py              &:: Gradio      → http://127.0.0.1:7860
```

Flask API examples:
```bash
curl http://127.0.0.1:5000/api/forecast
curl -X POST http://127.0.0.1:5000/predict -H "Content-Type: application/json" \
     -d '{"b_scalar":20,"bx":3,"by_gsm":5,"bz_gsm":-15,"speed":600,"density":10,"temperature":200000,"f107":150}'
```
Other routes: `GET /forecast`, `GET /api/live`, `GET /health`.

## Automation

- **Daily forecast** (`daily.yml`): see above. Manual run: **Actions → Daily forecast → Run workflow** (tick
  "dry run" to change nothing).
- **Weekly health checks** (`retrain.yml`, Mondays 03:00 UTC):
  1. Installs the pinned packages and runs the tests.
  2. Downloads fresh OMNI and GFZ data and rebuilds the hourly table.
  3. **Nowcaster:** retrains only if new data exists *and* its skill against persistence on the newest 6 months
     fell more than 0.10 below its test score; a new model is promoted only if its holdout RMSE ≤ 1.02 × the
     current model's.
  4. **Forecaster:** `src/forecast/monitor.py --act` (see above).
  5. Commits `models/`, `data/f107_history.csv`, `forecasts/monitor.json` and publishes to Hugging Face
     (`HF_TOKEN` repository secret).

Because the bots commit to `main`, run `git pull` before working locally.

## The Hugging Face Space (free, runs in the browser)
Hugging Face charges for server-hosted Gradio/Docker Spaces, so the Space is a free **static** Space that runs
`app/streamlit_app.py` **inside the visitor's browser** with [stlite](https://github.com/whitphx/stlite) (Streamlit on
Pyodide).
- The browser's Python can't load the scikit-learn pickles, so `src/portable.py` exports the nowcaster's trees to
  `models/current_portable.npz` and predicts with numpy (`tests/test_portable.py` shows identical predictions).
  The forecaster's tabs read the daily job's files; live re-forecasting in "Try the forecaster" needs the
  Streamlit app.
- Live data comes straight from NOAA, which allows browser access. GFZ doesn't, so in the browser the chart compares
  against NOAA's estimated Kp only.
- `app/hf_space/sync_hf.py --build-only <dir>` builds the Space locally; serve that folder with
  `python -m http.server` to test it.

## Documentation
- `PLAN.md` and `DECISIONS.md`: the forecaster plan and every decision with its reason and result.
- `docs/PROJECT_NOTES.md`: what each file does, how, why, and what it produced.
- `docs/report_notes.tex`: report and viva material, with figures. Compile on Overleaf; upload `docs/` plus
  `reports/figures`, `reports/v1/figures` and `reports/v2/figures` at the same relative paths.
- `TORMENTA_BUILD_PLAN.md`: the nowcaster's original plan, decision log and checklist.

## Data credits
NASA/GSFC Space Physics Data Facility OMNIWeb (OMNI2) · GFZ German Research Centre for Geosciences, Kp, Ap and
F10.7 (CC BY 4.0) · NOAA Space Weather Prediction Center real-time data and forecasts · Amazon Chronos-Bolt
(Apache 2.0). Not an operational warning service.
