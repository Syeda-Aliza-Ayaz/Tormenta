# Tormenta — Build Plan & Architecture (v2)

**Project:** Tormenta — predicting Earth's geomagnetic storm level (Kp index) from solar wind data.
**Course:** CT-378 Machine Learning, NED University (Fall 2026).
**Task type:** Supervised **regression** (target = Kp, continuous, 0–9).
**Framing:** A **nowcaster** — estimates current Kp from upstream (L1) solar-wind conditions, with an effective horizon of ~30–60 min (L1→Earth transit). Multi-day forecasting is out of scope (needs CME/solar imagery — "future work").

> This document is the single source of truth for the build. Follow the phases in order. The constraints in §0 are non-negotiable — violating any of them breaks the project, usually silently.
>
> **Team:** Alizeh, HRK. Notebooks are run in Anaconda Jupyter with the "Python 3.12 (tormenta)" kernel. After every phase, update `docs/PROJECT_NOTES.md` and `docs/report_notes.tex`.

---

## 0. Non-negotiable constraints (read first)

1. **No geomagnetic indices as features.** The model predicts Kp from *solar causes only*. Never use Kp, ap, Ap, Dst, AE, AL, AU, PCN as features. Allowed inputs: solar-wind + IMF fields and F10.7. Kp from GFZ is the **label only**.
   *Viva framing:* lagged Kp would not strictly be leakage (it is autoregression), but we exclude it by design so the model learns the solar-wind → Kp coupling and does not depend on a live Kp feed. Persistence is reported as a baseline to show what autoregression alone achieves.
2. **No train/serve skew.** Feature engineering is written **once** (`src/features.py`) and imported by both training and serving. Specifically:
   - Both sides feed `features.py` an **hourly** frame with the same raw columns (live 1-min/5-min data is resampled to hourly means first).
   - **Derived fields are recomputed from raw B/V/N/T on both sides** with the same code — OMNI's precomputed columns 11–15 (pressure, E-field, beta, Mach numbers) are **never** used. Pressure is computed *without* an alpha-particle correction (SWPC provides no alpha ratio).
3. **Causal features only.** Every feature at time *t* uses data at or before *t*. Rolling windows are **trailing**, never centered (this includes the F10.7 81-day mean — the textbook F10.7a is centered ±40 days and is leakage here).
4. **Complete time grid before shifting.** Reindex to a complete hourly grid (missing hours = NaN) before any `.shift()`/`.rolling()`, so lags never jump across data gaps.

---

## 1. Data sources

### Training tier (archival / batch)
| Role | Source | Notes |
|---|---|---|
| **Features** | NASA OMNI2 hourly | Phase 1 seed: OMNIWeb subset `.lst` + `.fmt` (1998-01-01 → 2026-01-10, 245,688 rows, ~2% missing). Automated retrain: SPDF yearly files `https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_YYYY.dat` (fixed 55-column format, separate parser). OMNI low-res lags real time by **months** (the seed ends 2026-01-10; checked Oct 2026). |
| **Target** | GFZ Potsdam Kp (`https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt`) | Daily rows with Kp1–Kp8 → 3-hourly. Last column `D`: 2 = definitive, 0/1 = preliminary. **Train only on D=2**; preliminary rows are for monitoring only. Licence CC BY 4.0. |

**OMNI subset columns used (from `.fmt`):** year, DOY, hour, Scalar B, Bx, By(GSM), Bz(GSM), proton temperature, proton density, flow speed, F10.7.
Dropped: columns 11–15 (recomputed instead, §0.2) and sunspot number (no clean live source; CC BY-NC; redundant with F10.7).

### Serving tier (live) — NOAA SWPC, no auth (`https://services.swpc.noaa.gov`)
| Data | Endpoint |
|---|---|
**Verified 2026-10-30.** The `products/solar-wind/{mag,plasma}-N-day.json` feeds originally planned here return **404** (retired), and `json/rtsw/*` only holds 24 h.

| Data | Endpoint |
|---|---|
| IMF (Bt, Bx/By/Bz **GSM**) + plasma (speed, density, temperature), 1-min | `/products/geospace/propagated-solar-wind.json`: **7 days**, active L1 spacecraft, **already propagated to Earth** (~50–75 min, field `propagated_time_tag`); values identical to the active source in `json/rtsw/` |
| Estimated Kp (3-hourly, comparison only) | `/products/noaa-planetary-k-index.json` (list of `{time_tag, Kp, …}`) |
| GFZ quick-look Kp (comparison; same producer as labels) | `https://kp.gfz.de/app/files/Kp_ap_nowcast.txt` |
| F10.7 | `/products/10cm-flux-30-day.json` (observed flux, matches GFZ `F10.7obs` within 0.5) on top of `data/f107_history.csv` (GFZ, refreshed by the slow loop) |

7 days of history comfortably covers the 24 h trailing windows plus a 48 h warm-up.

---

## 2. Architecture (two-speed loop)

```
   OMNI2 hourly (SPDF) ─┐
   GFZ Kp (D=2 only) ───┤
                        ▼
              data/processed/ (hourly) ──► train.py ──► models/current.joblib ◄── served by all 3 apps
                        ▲                                       ▲
                        │                                       │ promotes
              SLOW LOOP (weekly, GitHub Actions)                │
              update.py: fetch → preprocess → features →        │
              retrain → VALIDATION GATE ────────────────────────┘
                                                                │ loads
   SWPC propagated solar wind (7 d) ──► fetch_live.py ──► hourly means ──► features.py ──► predict
              FAST LOOP (minutes, inference only): predicted Kp vs SWPC estimated Kp + chart
```

---

## 3. Repository layout (repo root = `ML Project/`)

```
ML Project/
├── data/
│   ├── raw/                  # OMNI .lst/.fmt, GFZ .txt, SPDF yearly files (gitignored)
│   ├── processed/            # merged hourly dataset (parquet) — gitignored, rebuilt by update.py
│   └── f107_history.csv      # small rolling daily F10.7 file (committed; maintained by slow loop)
├── notebooks/
│   ├── 01_preprocessing.ipynb
│   ├── 02_eda.ipynb
│   └── 03_modeling.ipynb
├── src/
│   ├── config.py             # paths, columns, fill values, split years, Kp bins, endpoints
│   ├── ingest/
│   │   ├── fetch_omni.py      # parse OMNIWeb .lst AND SPDF omni2_YYYY.dat → same tidy hourly df
│   │   ├── fetch_gfz.py       # download GFZ, melt Kp1–Kp8 → 3-hourly kp + definitive flag
│   │   └── fetch_live.py      # SWPC → hourly df with the same raw columns as training
│   ├── preprocessing.py       # fills→NaN, complete hourly grid, merge kp label
│   ├── features.py            # SHARED: derived fields, lags, trailing rolling stats, coupling, time
│   ├── train.py               # split → baselines + models → tune → evaluate → save
│   ├── evaluate.py            # metrics + plots
│   ├── predict.py             # load current.joblib + feature frame → Kp (+ interval)
│   └── update.py              # slow-loop orchestrator
├── models/
│   ├── tormenta_vYYYYMMDD.joblib
│   ├── current.joblib
│   └── metrics_history.json
├── app/
│   ├── streamlit_app.py       # Streamlit Community Cloud — full dashboard
│   ├── flask_app/             # REST API + HTML front end (localhost)
│   └── hf_space/              # Gradio demo + model card (Hugging Face Space)
├── .github/workflows/retrain.yml
├── docs/                      # PROJECT_NOTES.md + report_notes.tex (living docs, updated every phase)
├── reports/figures/           # figures saved by notebooks for the report
├── requirements.txt           # pinned exact versions (runtime); requirements-dev.txt adds notebook/test tools
└── README.md
```

---

## 4. Pipeline stages

### Stage 1 — Ingest
- **OMNI** (`fetch_omni.py`): two parsers producing one schema (`time` UTC + raw columns). Replace fill values with NaN **per column** (`config.OMNI_FILL`: 999.9, 9999999., 9999., 999.9 …). Record source URL, licence, download date.
- **GFZ** (`fetch_gfz.py`): melt Kp1…Kp8 into a 3-hourly `kp` series with block start times 00,03,…,21 UT; carry the `D` flag.

### Stage 2 — Preprocess (`preprocessing.py`) — **hourly cadence**
- Reindex OMNI to a complete hourly grid.
- Label: each hour *h* gets the Kp of the 3-h block containing *h* (block start = floor(h/3)·3).
- Drop rows with missing label or `D≠2` from the training set.
- Imputation + scaling go **inside the sklearn `Pipeline`**, fitted on training data only. `StandardScaler` for KNN/SVR/Linear; HistGB handles NaN natively.
- Note: three consecutive hourly rows share one Kp label — ~245k rows but only ~82k independent labels. Never claim 245k independent samples.

### Stage 3 — Features (`features.py`, SHARED, pure function of an hourly frame)
- **Derived (recomputed, both sides):**
  - pressure `P = 1.6726e-6 · N · V²` (nPa, no alpha correction)
  - E-field `E = −V · Bz · 1e-3` (mV/m)
  - plasma beta `β = (4.16e-5·T + 5.34) · N / B²`
  - Alfvén Mach `M_A = V · √N / (20 · B)`
  - clock angle features: `B_T = √(By²+Bz²)`, `sin(θ/2)`, Newell-style coupling `V^(4/3) · B_T^(2/3) · sin^(8/3)(θ/2)`
  - **Validation (Phase 3, once):** compare recomputed β and M_A against OMNI columns 13–14 (should match closely, same definitions) and P against column 11 (expect a near-constant ratio from OMNI's alpha factor), *then* drop OMNI's columns.
- **Coupling:** `V·Bz`, `V·Bs` where `Bs = max(−Bz, 0)`.
- **Lags:** Bz, V, N at t−1h, t−3h, t−6h, t−9h.
- **Trailing rolling:** mean & std of Bz and V over 3 h / 6 h / 9 h; min Bz and max V over 3 h (keeps storm peaks).
- **F10.7:** previous day's value (daily F10.7 is measured ~20 UT, so same-day value is unavailable for most of the day) + **trailing** 81-day mean.
- **Cyclical time:** sin/cos of hour-of-day and day-of-year.
- Target feature count > 15.

### Stage 4 — Train (`train.py`)
- **Split (time-ordered):** train 1998–2016 / val 2017–2019 / test 2020–latest definitive.
  - `TimeSeriesSplit(n_splits=5)` CV runs **within train** for hyperparameter tuning.
  - Val is for **model selection** across families.
  - Chosen config is refit on train+val, then evaluated **once** on test.
- **Baselines:** persistence (Kp of previous 3-h block) and Linear Regression.
- **Models:** KNN, SVR, Random Forest, HistGradientBoosting.
  - KNN and SVR are tuned on a **strided** subsample of ~15–20k training rows (e.g. every 8th–10th hour), not random — keeps rows chronological so `TimeSeriesSplit` folds stay meaningful, and still spans both solar cycles (a contiguous-recent slice would not). Kernel SVR is O(n²–n³); stated in report.
- **Ablation:** sample weights `1 + Kp/3` vs unweighted (storm under-prediction).
- **Evaluation:** MAE, RMSE, R²; residual plot, error by storm level (Kp bins 0–3, 4, 5, 6, 7+), feature importance, comparison table, over/under-fitting discussion.
- **Production model:** HistGB (small, NaN-native). Interval from quantile HistGB (`loss="quantile"`, α = 0.1 / 0.9). RF stays in the comparison table only.
  - The point model (squared error) and the quantile models are separate fits, so the point can occasionally fall outside the band. `predict.py` reports `lo = min(q10, point)`, `hi = max(q90, point)`, and the report notes it. The point stays the squared-error model so the RMSE-based comparison is consistent.
- **Save:** `models/tormenta_vYYYYMMDD.joblib`, copy to `current.joblib`, append to `models/metrics_history.json`.

### Stage 5 — Deploy (all three load `current.joblib`, import `features.py`/`predict.py`/`fetch_live.py`)
- **Streamlit** — full dashboard: manual input + "Use live data", predicted Kp + interval, predicted-vs-SWPC-estimated timeline.
- **Hugging Face Space** — Gradio demo + model card.
- **Flask** — `/predict` REST endpoint + HTML form, input validation and error messages, localhost.
- **scikit-learn pinned to one exact version everywhere** (joblib pickles break across versions).

### Stage 6 — Slow loop (`update.py` + `retrain.yml`)
1. Fetch SPDF OMNI + GFZ; **rebuild `data/processed/` from scratch** each run (it is gitignored, never committed). Refresh `data/f107_history.csv`.
2. Retrain the chosen configuration.
3. **Validation gate (no model is ever scored on data it trained on):**
   - Gate holdout = the most recent 6 months of **definitive** (D=2) labels.
   - Production models are always trained with cutoff = start of that holdout (no refit-on-all). Both the current model (older cutoff) and the candidate (cutoff = holdout start) are therefore unseen on the holdout.
   - **Both models are scored on this run's holdout, in this run.** Never reuse the incumbent's stored RMSE — it was measured on an older slice.
   - Promote if candidate RMSE ≤ current RMSE × 1.02. Else keep current and log.
   - Cost: production lacks the latest ~6 months of a ~28-year record — negligible.
4. Version, update `current.joblib`, append `models/metrics_history.json`.
5. **Redeploy:** commit + push **only** `models/` and `data/f107_history.csv` → Streamlit Cloud rebuilds on push; HF Space synced explicitly via `huggingface_hub.upload_file` (it is a separate git repo); Flask reloads on restart.

```yaml
# .github/workflows/retrain.yml
on:
  schedule: [{ cron: "0 0 * * 1" }]   # Mondays 00:00 UTC
  workflow_dispatch: {}
permissions:
  contents: write
jobs:
  retrain:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python -m src.update
      - run: |
          git config user.name  "tormenta-bot"
          git config user.email "bot@users.noreply.github.com"
          git add models/ data/f107_history.csv
          git diff --cached --quiet && echo "no changes" && exit 0
          git commit -m "auto-retrain $(date -u +%F)"
          git push
      - run: python -m src.sync_hf     # uploads current.joblib to the HF Space
        env: { HF_TOKEN: "${{ secrets.HF_TOKEN }}" }
```

---

## 5. Build order

- **Phase 0:** git init, scaffold, move data to `data/raw/`, `config.py`, `.gitignore`, `requirements.txt`, venv (Python 3.12 — same version on Streamlit Cloud, HF Space `python_version`, Actions).
- **Phase 1:** `fetch_omni.py` (.lst parser; SPDF parser can wait for Phase 6) + `fetch_gfz.py` + `preprocessing.py` → hourly processed dataset, run via `01_preprocessing.ipynb`. Print rows, features, missing-% per column.
- **Phase 2:** `02_eda.ipynb` — ≥5 plots (distributions, missingness, Bz–Kp relationship, storm-level balance, a known storm e.g. May 2024).
- **Phase 3:** `features.py` + `train.py` + `evaluate.py` → baselines + 4 models, tuned, ablation, test metrics, plots, saved model.
- **Phase 4:** `predict.py` + `fetch_live.py` → working live nowcast.
- **Phase 5:** three deployments.
- **Phase 6:** SPDF parser + `update.py` + `sync_hf.py` + `retrain.yml`.
- **Phase 7:** README (setup + 3 links) + report assets.

---

## 6. Notes & report/viva points
- **Propagation offset:** resolved in Phase 4. SWPC's propagated product is already shifted to Earth, like OMNI, so live and training timing match. Because L1 data arrives ~1 h before it hits Earth, the newest live hour is a short-range forecast (flagged `ahead`).
- **Label non-independence:** ~245k hourly rows, ~82k independent Kp labels.
- **Storm imbalance:** Kp ≥ 5 is a few percent of rows; report error by storm level and the weighting ablation.
- **Deliberate held-out extreme:** the May 2024 (Gannon, G5) storm falls in the 2020+ test set — an honest test of extreme-event generalization. Expect and discuss under-prediction at Kp 8–9.
- **Subsampling:** SVR/KNN tuned on a strided subsample (chronology preserved); stated with its size.
- **Live gaps:** SWPC plasma can be NaN at low density — HistGB handles NaN; imputation runs inside the pipeline at inference.
- **Live validation:** against SWPC estimated Kp immediately; GFZ definitive Kp retrospectively.
- **No secrets** except `HF_TOKEN` as a GitHub Actions secret.
- **Future work:** MLflow/Airflow orchestration, solar imagery / CME inputs for longer horizons.

---

## 7. Decision log (v1 → v2, from design review)

| # | Issue in v1 | Decision in v2 |
|---|---|---|
| 1 | 3-h block aggregation used in-block (future) data unavailable mid-block live | Hourly cadence, trailing windows ending at *h*, label = Kp of block containing *h* |
| 2 | OMNI (bow-shock-shifted, hourly) ≠ SWPC (raw L1, 1–5 min) | Phase 4: use SWPC's *propagated* 1-min feed (Earth-shifted) and average to OMNI-style hourly means |
| 3 | Derived fields taken from OMNI precomputed columns | Recompute P, E, β, M_A from raw fields on both sides; no alpha correction |
| 4 | `*-5-minute.json` too short for 9 h lags + rolling | Use `*-1-day.json` (3-day fallback) |
| 5 | Sunspot number had no live source; CC BY-NC | Dropped; F10.7 kept |
| 6 | F10.7 81-day mean is centered by convention (leakage) | Trailing 81-day mean; previous day's F10.7 (same-day value published ~20 UT) |
| 7 | Retrain loop could not re-download temp-named `.lst` | SPDF `omni2_YYYY.dat` parser for the loop. (A v2 note claiming "lags days" came from misreading DOY as month — OMNI lags months.) |
| 8 | Redeploy: HF not synced by GitHub push; no push permission; wrong metrics path; RF size | `sync_hf.py` step, `contents: write`, `models/metrics_history.json`, ship HistGB |
| 9 | Gate compared models on different slices; refit-on-all would leak gate data | Shared 6-month definitive holdout, models trained to holdout start, 2% tolerance |
| 10 | `.shift()` across gaps gives wrong lags | Reindex to complete hourly grid first |
| 11 | Preliminary GFZ labels get revised | Train on D=2 only |
| 12 | Kernel SVR infeasible at full size | SVR/KNN tuned on 15–20k subsample |
| 13 | Storm under-prediction | `1 + Kp/3` weight ablation; error by storm level |
| 14 | Interval method unspecified | Quantile HistGB (α 0.1 / 0.9) |
| 15 | Val set role unclear | CV within train → val for selection → refit train+val → single test eval |
| 16 | joblib pickles break across versions | Exact sklearn pin across all apps |
| 17 | Lagged Kp described as "leakage" | Reframed as autoregression excluded by design; persistence as baseline |
| 18 | Weekly commit of `data/processed/` bloats repo | Gitignore it; `update.py` rebuilds from raw each run; commit only models + F10.7 history |
| 19 | Incumbent's cached RMSE was from an older holdout | Re-score both models on the current holdout every run |
| 20 | Fetching 81 days of F10.7 live is fragile | Slow loop maintains `data/f107_history.csv`; app reads it |
| 21 | Random subsample breaks `TimeSeriesSplit` chronology | Strided subsample (spans both cycles, stays ordered) |
| 22 | Point model can fall outside separately-fit quantile band | Band widened to include point; noted in report |
| 23 | Recomputed derived fields unverified | One-off comparison against OMNI cols 11, 13, 14 before dropping them |
| 24 | OMNI `f107` column vs live SWPC observed flux | Use GFZ `F10.7obs` (observed Penticton flux, same quantity SWPC serves) for training and the history file |
| 25 | Interval coverage 75.7% < 80% | CQR margin from out-of-fold train years + validation, stored in the bundle |
| 26 | Exponential storm memory over all history would differ live (3-day feed) | Fixed 48 h window; `MIN_HISTORY_HOURS` = 48 |
| 27 | Repeated test evaluation erodes trust | v3 is the last round; decisions on CV + val only; then freeze |
| 28 | Planned SWPC 3-day solar-wind feeds retired (404); RTSW only 24 h | `products/geospace/propagated-solar-wind.json` (7 d, Earth-propagated, GSM) |
| 29 | NOAA estimated Kp differs from our label source | Compare live against GFZ quick-look Kp too (same producer as labels) |

---

## 8. Build checklist

### Phase 0 — Scaffold
- [x] `git init`; `.gitignore` (venv, `data/raw/`, `data/processed/`, `__pycache__`, `.ipynb_checkpoints`)
- [x] Move OMNI `.lst`/`.fmt` and GFZ `.txt` into `data/raw/`
- [x] Create folder layout (§3) with `__init__.py` files
- [x] Python 3.12 venv (`py -3.12 -m venv .venv`); `requirements.txt` with exact pins (incl. one sklearn version)
- [x] `src/config.py`: paths, OMNI columns + per-column fill values, split years, Kp bins, SWPC endpoints, gate tolerance

### Phase 1 — Ingest & preprocess
- [x] `fetch_omni.py` parses `.lst`; fills → NaN per column; UTC `time` from year+DOY+hour
- [x] `fetch_gfz.py` melts Kp1–Kp8 → 3-hourly with block starts 00…21 UT; keeps `D` flag
- [x] `preprocessing.py`: complete hourly grid, block-containing-hour label, definitive flag kept (D=2 filter applied in `train.py`)
- [x] Save `data/processed/` (CSV for now; parquet once pyarrow is installed); print rows, columns, missing-% per column
- [x] Sanity check: no duplicate timestamps; hourly grid has no holes; Kp ∈ [0, 9]

### Phase 2 — EDA
- [x] Distributions of key fields and Kp
- [x] Missingness plot
- [x] Bz (and V·Bs) vs Kp
- [x] Storm-level balance (Kp bins)
- [x] Time series of a known storm (May 2024)
- [x] Extra: gap-length analysis, lag correlation, solar-cycle split view, extreme-value check (figures in `reports/figures/`)

### Phase 3 — Features & modeling
- [x] **EDA follow-ups:** 12 h / 24 h speed means added (live needs SWPC 3-day feed); F10.7 flare spikes masked (> 2× trailing 27-day median); selection reads CV + val + storm RMSE together
- [x] `features.py` pure function of hourly frame; derived fields recomputed; OMNI cols 11–15 unused
- [x] One-off check: recomputed β, M_A ≈ OMNI cols 13–14; P / OMNI col 11 ≈ constant ratio
- [x] All rolling windows trailing (incl. F10.7 81-day); F10.7 uses previous day
- [x] Unit test: features at *t* unchanged when future rows are appended (causality check)
- [x] Feature count > 15
- [x] Split 1998–2016 / 2017–2019 / 2020+; `TimeSeriesSplit(5)` within train
- [x] Baselines: persistence, Linear Regression
- [x] KNN + SVR (strided subsample), RF, HistGB tuned
- [x] Model selection on val; refit train+val; single test evaluation
- [x] Weighting ablation `1 + Kp/3`
- [x] Quantile HistGB for interval; band widened to include point estimate
- [x] Plots: residuals, error by storm level, feature importance; comparison table
- [x] Save versioned model, `current.joblib`, `models/metrics_history.json`
- [x] **Full training run** of `03_modeling.ipynb` (28 Oct 2026, ~20 min): HistGB test RMSE 0.585 / R² 0.80 (persistence 0.862); 80% interval coverage 77% test, 78% gate holdout; production `tormenta_v20261028`

### Phase 3b — Improvement round (v1 → v2)
- [x] Archive v1 results (`reports/v1/`); diagnose v1 error by block hour (first hour worst)
- [x] v2 features: block position + block-so-far stats, pressure dynamics, 12/24 h Newell; leakage tests (7 total)
- [x] Wider HistGB search (20); equal-weight ensemble; fair gate (both models on same holdout, same run, asserted unseen)
- [x] Past-Kp ablation (validation only, never production)
- [x] Team runs `04_improvements.ipynb` → adopt v2 only if CV **and** val improve (rule fixed in advance)
- [x] Team re-runs `03_modeling.ipynb` → v2 test once; gate vs v1; docs updated with v1 vs v2

### Phase 3c — Final round (v2 → v3), then freeze
- [x] Archive v2 results (`reports/v2/`)
- [x] Storm-memory features (fixed 48 h decay window, train = live), monotonic constraints, CQR conformal margin
- [x] Learning + complexity curves (underfitting check); 2 new tests (9 total)
- [x] Team runs `05_final_round.ipynb` → storm memory and monotonic both rejected (flags off); not underfitting; CQR adopted
- [x] Team re-runs `03_modeling.ipynb` → v3 test once (= v2 metrics); coverage 75.7% → 80.8%; promoted; **model frozen**

### Phase 4 — Live nowcast
- [x] Verify SWPC endpoint shapes → old 3-day feeds retired; switched to the propagated 7-day feed (decision 28)
- [x] `fetch_live.py` → hourly frame with training's raw columns (OMNI-style hourly means, ≥ 20 min per hour)
- [x] `data/f107_history.csv` from GFZ `F10.7obs` + SWPC 30-day feed for the newest days
- [x] `predict.py`: `predict_hourly` / `nowcast()` return Kp + interval + `ahead` flag
- [x] Parity test: SWPC-shaped minutes → live path gives identical features to the training path (14 tests)
- [x] `06_live_nowcast.ipynb`: live snapshot vs GFZ quick-look and NOAA estimated Kp (figure 16)

### Phase 5 — Deployments
- [ ] Streamlit: manual input, live data, interval, predicted-vs-SWPC timeline → public URL
- [ ] HF Space: Gradio demo + model card → public URL
- [x] Flask: `/predict` + HTML form + validation/error messages + `/live`, `/api/live`, `/health` → localhost (9 tests)
- [ ] All three load the same `current.joblib` with the same pinned sklearn

### Phase 6 — Slow loop
- [ ] SPDF `omni2_YYYY.dat` parser → same schema as `.lst` parser (test on overlapping year)
- [ ] `update.py`: fetch → rebuild processed from scratch → refresh F10.7 history → retrain to holdout start → gate → promote/log
- [ ] Gate verified: neither model trained on the holdout; both scored on it in the same run (no cached RMSE)
- [ ] Workflow commits only `models/` + `data/f107_history.csv`
- [ ] `sync_hf.py` + `HF_TOKEN` secret
- [ ] `retrain.yml` with `contents: write`; manual `workflow_dispatch` run succeeds

### Phase 7 — Wrap-up
- [ ] README: setup, run instructions, 3 deployment links
- [ ] Report assets: comparison table, plots, decision log
- [ ] Viva points (§6) written up: propagation offset, autoregression vs leakage, label non-independence, weighting ablation
