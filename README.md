# Tormenta: geomagnetic Kp nowcast

Tormenta predicts the planetary **Kp index** (0–9, the standard 3-hourly measure of geomagnetic disturbance)
from solar-wind measurements taken about an hour upstream of Earth, with an 80% prediction interval.
CT-378 Machine Learning, NED University, Fall 2026 · **Alizeh & HRK**.

| | |
|---|---|
| **Live app (Streamlit)** | <https://tormenta.streamlit.app/> |
| **Model + model card (Hugging Face)** | <https://huggingface.co/aliza-ayaz/tormenta> |
| **Project page (Hugging Face Space)** | <https://huggingface.co/spaces/aliza-ayaz/tormenta> |
| **Flask app** | runs locally (see below) |

## Results (test years 2020 → Jan 2026, never used for training or model selection)

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
- **Over time:** on Jan–Jun 2026, unseen by the model, RMSE is 0.579, so there is no sign of drift.

## How it works

```
NASA OMNI2 hourly (1998→) ─┐                         ┌─► weekly retrain (GitHub Actions) ─► validation gate ─► models/current.joblib
GFZ definitive Kp (labels) ┴─► hourly table ─► src/features.py (shared) ─► HistGB + quantile models + conformal margin
NOAA SWPC real-time feeds ──► hourly means ──────────┘                      └─► Streamlit · Flask · Gradio · HF model repo
```

- **Inputs:** IMF |B|, Bx, By, Bz (GSM), proton speed, density, temperature, and F10.7 flux. **No geomagnetic
  indices** are used as inputs.
- **Features:** 66 causal (trailing-only) features: coupling functions, pressure, lags, 3–24 h statistics,
  position inside the 3-h Kp block, and time of day and year. One shared `src/features.py` is used for training
  and live serving, and a parity test checks they match.
- **Model selection:** time-ordered splits (train 1998–2016, validation 2017–2019, test 2020+) with
  `TimeSeriesSplit` CV. Every improvement was decided on CV + validation by a rule fixed in advance, and the test
  set was scored once per version.

## Repository layout

```
src/            config, ingest (OMNI .lst + SPDF yearly files, GFZ, live SWPC), preprocessing, features,
                train, evaluate, predict, update (weekly retrain)
notebooks/      01 preprocessing · 02 EDA · 03 modelling · 04 v1→v2 · 05 final round · 06 live nowcast
app/            streamlit_app.py · flask_app/ · hf_space/ (Gradio app, model card, landing page, sync_hf.py)
models/         current.joblib (production) + earlier versions + metrics_history.json
reports/        figures/ and metrics/ (v1 and v2 archived in reports/v1, reports/v2)
tests/          leakage, live parity, SPDF parser, apps, retrain guard rails
docs/           PROJECT_NOTES.md (what/why per file) · report_notes.tex (report + viva material)
.github/workflows/retrain.yml   weekly retrain
```

## Setup (Windows, Python 3.12)

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m ipykernel install --user --name tormenta --display-name "Python 3.12 (tormenta)"
```

Use Python **3.12** and the exact pins: the model is a pickled scikit-learn 1.9.1 object, and the code warns if
the version differs.

**Data** (`data/raw/`, not in git):
- The OMNIWeb subset `omni2_*.lst` + `.fmt` (1998-01-01 onward: |B|, Bx, By/Bz GSM, T, N, V, pressure, E, β,
  Mach numbers, R, F10.7).
- The GFZ file `Kp_ap_Ap_SN_F107_since_1932.txt` from <https://kp.gfz.de>.

Alternatively, `python -m src.update --dry-run` downloads everything from NASA SPDF and GFZ and rebuilds
`data/processed/` (needs access to spdf.gsfc.nasa.gov).

## Run

**Notebooks** (Anaconda Jupyter, kernel "Python 3.12 (tormenta)"). Use **Kernel → Restart & Run All**,
in this order:

| Notebook | What it does | Time |
|---|---|---|
| `01_preprocessing` | builds `data/processed/tormenta_hourly.csv` | ~1 min |
| `02_eda` | figures 01–08 | ~2 min |
| `03_modeling` | tunes all models, single test evaluation, production model + gate | ~40 min |
| `04_improvements` | v1 vs v2 features on CV + validation | ~20 min |
| `05_final_round` | underfitting curves, v3 variants, conformal calibration | ~40 min |
| `06_live_nowcast` | live prediction vs GFZ and NOAA Kp (needs internet) | ~1 min |

`03`–`05` are the record of how the model was built. The final model is already in `models/current.joblib`, so
you only need `01`, `02` and `06` to reproduce the data, plots and live check.

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

Flask API example:
```bash
curl -X POST http://127.0.0.1:5000/predict -H "Content-Type: application/json" \
     -d '{"b_scalar":20,"bx":3,"by_gsm":5,"bz_gsm":-15,"speed":600,"density":10,"temperature":200000,"f107":150}'
```
Other routes: `GET /api/live`, `GET /health`. Manual inputs are assumed to have held steady for the past 3 days,
because the model also uses lags and 24-h averages.

**From Python**
```python
from src.predict import load_bundle, nowcast
pred, hourly = nowcast(load_bundle())   # kp_pred, kp_lo, kp_hi, ahead (hour after "now")
```

## Weekly retraining

`.github/workflows/retrain.yml` runs every Monday 03:00 UTC, and on demand under **Actions → Weekly retrain →
Run workflow**. A dry run is the default for manual runs.

What it does:
1. Installs the pinned packages and runs the tests.
2. Downloads fresh OMNI (SPDF) and GFZ data and rebuilds the hourly table.
3. Retrains the **frozen** configuration up to the start of a 6-month holdout of definitive Kp.
4. Promotes the new model only if its holdout RMSE is ≤ 1.02 × the current model's. Both models are scored on
   that holdout in the same run.
5. Commits `models/` + `data/f107_history.csv` and publishes the new model to Hugging Face, using the `HF_TOKEN`
   repository secret.

Because the bot commits to `main`, run `git pull` before working locally.

## Documentation
- `docs/PROJECT_NOTES.md`: what each file does, how, why, and what we got.
- `docs/report_notes.tex`: report and viva material, with figures. Compile on Overleaf; upload `docs/` plus
  `reports/figures`, `reports/v1/figures` and `reports/v2/figures` at the same relative paths.
- `TORMENTA_BUILD_PLAN.md`: plan, decision log and checklist.

## Data credits
NASA/GSFC Space Physics Data Facility OMNIWeb (OMNI2) · GFZ German Research Centre for Geosciences, Kp and
F10.7 (CC BY 4.0) · NOAA Space Weather Prediction Center real-time data. Not an operational warning service.
