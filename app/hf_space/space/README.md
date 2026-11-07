---
title: Tormenta Kp Nowcast
emoji: 🧲
colorFrom: indigo
colorTo: purple
sdk: static
app_file: index.html
pinned: false
short_description: Live Kp nowcast from solar wind (Streamlit in the browser)
---

**Tormenta**: a live nowcast of the geomagnetic Kp index from solar-wind data.

This Space runs the project's Streamlit app **in your browser** with [stlite](https://github.com/whitphx/stlite)
(Streamlit on Pyodide), using the same feature code as training and live data fetched from NOAA SWPC. The model is
the exported tree ensemble (`models/current_portable.npz`), whose predictions are identical to the scikit-learn
model's.

- Model + model card: <https://huggingface.co/aliza-ayaz/tormenta>
- Server version: <https://tormenta.streamlit.app/>
- Code: <https://github.com/Syeda-Aliza-Ayaz/Tormenta>
