---
library_name: sklearn
pipeline_tag: tabular-regression
tags:
- space-weather
- geomagnetic-storms
- kp-index
- solar-wind
- scikit-learn
- tabular-regression
metrics:
- rmse
- mae
- r2
---

# Tormenta: geomagnetic Kp nowcast

Tormenta predicts the planetary **Kp index** (0–9, the standard 3-hourly measure of geomagnetic
disturbance) from the solar wind measured upstream of Earth. It is a CT-378 Machine Learning project
(NED University, Fall 2026) by Alizeh and HRK. Code: <https://github.com/Syeda-Aliza-Ayaz/Tormenta>

## Model card

| | |
|---|---|
| **Task** | Regression: hourly Kp nowcast with an 80% prediction interval |
| **Model** | scikit-learn `HistGradientBoostingRegressor` (point), plus q10/q90 quantile models with a conformal (CQR) margin |
| **Inputs** | IMF \|B\|, Bx, By, Bz (GSM), proton speed, density, temperature, F10.7 solar flux; 66 engineered features (derived physics, lags, trailing means, position in the 3-h Kp block, time of day/year) |
| **Not used as inputs** | Any geomagnetic index (Kp, Dst, AE, …), so the nowcast does not wait for magnetometer data |
| **Training data** | NASA OMNI2 hourly from 1998, up to 6 months before the newest definitive Kp (retrained weekly; cutoff in `models/metrics_history.json`); labels are GFZ Potsdam definitive Kp |
| **Selection** | Time-ordered CV in 1998–2016, validation 2017–2019, one final test on 2020 to 2026-01 |
| **Live inputs** | NOAA SWPC propagated solar wind (1-min, time-shifted to Earth), averaged to hours like OMNI |

### Test results (2020 to 2026-01, 52,848 hours, includes the May 2024 G5 storm)

| Metric | Tormenta | Persistence baseline |
|---|---|---|
| RMSE | **0.573** | 0.862 |
| MAE | 0.437 | 0.643 |
| R² | 0.808 | 0.566 |
| RMSE on storm hours (Kp ≥ 5−) | **0.846** | 1.368 |
| 80% interval coverage | 80.8% | – |

### Intended use and limitations
- **Intended use:** education and situational awareness. It is **not** an operational warning service; for
  that, use NOAA SWPC or GFZ.
- **Big storms are under-predicted:** about −0.6 Kp on average for G3+ hours, because such storms are rare in
  the training data.
- **Sudden onsets show up 1–2 h late** within a 3-hour Kp block.
- **Lead time:** at most about 1 h, the travel time of the solar wind from L1 to Earth.
- **Manual inputs** (`predict_steady`) are assumed to have held steady for the past 3 days, because the model also
  uses lags and 24-h averages.

## Use the model

**Live demo:** <https://huggingface.co/spaces/aliza-ayaz/tormenta> (runs in your browser) · <https://tormenta.streamlit.app/> (server)

This repository contains the model (`models/current.joblib`; the same trees as numpy arrays in `models/current_portable.npz`, loadable with `src.portable.load_portable` without scikit-learn), the feature and prediction code it needs
(`src/`), and the F10.7 history file used for the trailing solar-flux mean. Requires Python 3.12 and the exact
package versions in `requirements.txt`; the model is a pickled scikit-learn 1.9.1 object.

```python
import sys
from huggingface_hub import snapshot_download

path = snapshot_download("aliza-ayaz/tormenta")
sys.path.insert(0, path)

from src.predict import load_bundle, nowcast, predict_steady

bundle = load_bundle(f"{path}/models/current.joblib")

# Live: fetch NOAA SWPC real-time solar wind, predict every recent hour
pred, hourly = nowcast(bundle)
print(pred.tail(3))            # kp_pred, kp_lo, kp_hi (80% interval), ahead

# Manual: one set of conditions, assumed steady for the past 3 days
print(predict_steady(bundle, {"b_scalar": 20, "bx": 3, "by_gsm": 5, "bz_gsm": -15, "speed": 600,
                              "density": 10, "temperature": 2e5, "f107": 150}))
```

The bundle is a dict with `point`, `q_lo`, `q_hi` (fitted `HistGradientBoostingRegressor`s), `features`
(the 66 column names), `interval_margin`, `trained_until` and `version`. Build features only with
`src.features.build_features`, which is the same code used in training.

### Data and licences
NASA/GSFC Space Physics Data Facility OMNIWeb; GFZ German Research Centre for Geosciences Kp and F10.7
(CC BY 4.0); NOAA Space Weather Prediction Center real-time data (public domain).
