---
title: Tormenta Kp Nowcast
emoji: 🧲
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 6.31.0
python_version: "3.12"
app_file: app.py
pinned: false
short_description: Nowcast of the geomagnetic Kp index from solar wind
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
| **Training data** | NASA OMNI2 hourly, 1998 to 2025-07; labels are GFZ Potsdam definitive Kp |
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
- **Manual inputs** in this demo are assumed to have held steady for the past 3 days, because the model also
  uses lags and 24-h averages.

### Data and licences
NASA/GSFC Space Physics Data Facility OMNIWeb; GFZ German Research Centre for Geosciences Kp and F10.7
(CC BY 4.0); NOAA Space Weather Prediction Center real-time data (public domain).
