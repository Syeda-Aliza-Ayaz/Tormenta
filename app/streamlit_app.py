"""Tormenta Streamlit dashboard: live Kp nowcast, manual input, model card.

Local:  .venv\\Scripts\\streamlit run app\\streamlit_app.py
Cloud:  Streamlit Community Cloud, main file app/streamlit_app.py, Python 3.12, requirements.txt at repo root.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
import streamlit as st  # noqa: E402

from src import config, evaluate as ev  # noqa: E402
from src.ingest import fetch_live  # noqa: E402
from src.predict import INPUT_LIMITS, load_bundle, nowcast, predict_steady, storm_level, validate_inputs  # noqa: E402

st.set_page_config(page_title="Tormenta Kp Nowcast", page_icon="🧲", layout="wide")

DEFAULTS = {"b_scalar": 5.0, "bx": 1.0, "by_gsm": 2.0, "bz_gsm": 0.0, "speed": 400.0, "density": 5.0,
            "temperature": 100000.0, "f107": 120.0}
STEPS = {"speed": 10.0, "temperature": 10000.0, "f107": 1.0}
LEVEL_NOTE = {"0-3": "quiet to unsettled", "4": "active", "5 (G1)": "minor storm", "6 (G2)": "moderate storm",
              "7+ (G3-G5)": "strong to extreme storm"}


@st.cache_resource
def get_bundle():
    return load_bundle()


@st.cache_data(ttl=300, show_spinner="Fetching real-time data from NOAA SWPC…")
def get_live():
    pred, hourly = nowcast(get_bundle())
    live = pred
    for fetch, name in [(fetch_live.fetch_gfz_nowcast, "kp_gfz"), (fetch_live.fetch_swpc_kp, "kp_swpc")]:
        try:
            live = ev.attach_block_kp(live, fetch(), name)
        except requests.RequestException:
            pass                                    # comparison only; the nowcast still works
    return live, hourly, fetch_live.fetch_f107()


def show_kp(col, title, row, note=None):
    level = storm_level(row["kp_pred"])
    col.metric(title, f"Kp {row['kp_pred']:.1f}", f"{level} · {LEVEL_NOTE[level]}", delta_color="off")
    col.caption(f"80% range {row['kp_lo']:.1f}–{row['kp_hi']:.1f}" + (f" · {note}" if note else ""))


bundle = get_bundle()
st.title("Tormenta: geomagnetic Kp nowcast")
st.caption("Predicts the planetary Kp index (0–9) from solar-wind conditions with a HistGradientBoosting model "
           "trained on 1998–2025 NASA OMNI data and GFZ definitive Kp. Live inputs come from NOAA SWPC.")

live_tab, manual_tab, about_tab = st.tabs(["Live nowcast", "Try your own inputs", "About the model"])

with live_tab:
    if st.button("Refresh live data"):
        get_live.clear()
    try:
        live, hourly, f107 = get_live()
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        st.error(f"Could not get live data from NOAA SWPC ({type(exc).__name__}). Try again in a minute.")
        live = None
    if live is not None and len(live):
        past, ahead = live[~live["ahead"]], live[live["ahead"]]
        c1, c2, c3 = st.columns(3)
        show_kp(c1, f"Now ({past.index[-1]:%d %b %H:00} UTC)", past.iloc[-1])
        if len(ahead):
            show_kp(c2, f"Next hour ({ahead.index[-1]:%H:00} UTC)", ahead.iloc[-1],
                    "solar wind already measured at L1, ~1 h before it reaches Earth")
        latest = hourly.dropna().iloc[-1]
        c3.metric("Solar wind now", f"{latest['speed']:.0f} km/s", f"Bz {latest['bz_gsm']:+.1f} nT", delta_color="off")
        c3.caption(f"|B| {latest['b_scalar']:.1f} nT · density {latest['density']:.1f} cm⁻³ · "
                   f"F10.7 {f107.dropna().iloc[-1]:.0f}")

        st.pyplot(ev.plot_live(live), clear_figure=True)

        if "kp_gfz" in past:
            scored = past.dropna(subset=["kp_gfz"])
            if len(scored):
                m = ev.metrics(scored["kp_gfz"], scored["kp_pred"])
                cover = ((scored["kp_gfz"] >= scored["kp_lo"]) & (scored["kp_gfz"] <= scored["kp_hi"])).mean()
                st.caption(f"Last {len(scored)} hours vs GFZ quick-look Kp: RMSE {m['rmse']:.2f}, "
                           f"MAE {m['mae']:.2f}, 80% range covered {cover:.0%} (test-set RMSE was 0.57).")

        with st.expander("Hourly table (last 24 h)"):
            table = live.tail(24).iloc[::-1].copy()
            table["level"] = table["kp_pred"].map(storm_level)
            st.dataframe(table.round(2), width="stretch")

with manual_tab:
    st.write("Enter one set of solar-wind conditions. The model also uses lags and 6–24 h averages, so the "
             "values are **assumed to have held steady for the past 3 days**.")
    if st.button("Fill with the latest live values"):
        try:
            _, hourly, f107 = get_live()
            latest = hourly.dropna().iloc[-1]
            for c in config.SW_FEATURES:
                st.session_state[c] = float(round(latest[c], 2))
            st.session_state["f107"] = float(f107.dropna().iloc[-1])
        except (requests.RequestException, ValueError, KeyError, IndexError):
            st.error("Live data unavailable right now.")
    for name, value in DEFAULTS.items():
        st.session_state.setdefault(name, value)
    with st.form("manual"):
        cols = st.columns(4)
        raw = {}
        for i, (name, (lo, hi, label)) in enumerate(INPUT_LIMITS.items()):
            raw[name] = cols[i % 4].number_input(label, min_value=lo, max_value=hi, step=STEPS.get(name, 0.5),
                                                 key=name)
        submitted = st.form_submit_button("Predict Kp")
    st.caption("Southward Bz (negative) and high speed drive storms. Try Bz −20 and speed 700.")
    if submitted:
        values, errors = validate_inputs(raw)
        if errors:
            for msg in errors.values():
                st.error(msg)
        else:
            out = predict_steady(bundle, values)
            st.metric("Predicted Kp", f"{out['kp_pred']:.1f}",
                      f"{out['level']} · {LEVEL_NOTE[out['level']]}", delta_color="off")
            st.caption(f"80% range {out['kp_lo']:.1f}–{out['kp_hi']:.1f}")

with about_tab:
    st.markdown(f"""
**Model:** `{bundle['version']}`, trained on definitive data up to {bundle['trained_until'][:10]}
({len(bundle['features'])} features; HistGradientBoosting point model + q10/q90 quantile models with a conformal
margin of {bundle.get('interval_margin', 0):+.3f} Kp).

| Test set 2020 → 2026-01 (never used for training or selection) | Value |
|---|---|
| RMSE | 0.573 Kp |
| MAE | 0.437 Kp |
| R² | 0.808 |
| RMSE on storm hours (Kp ≥ 5−) | 0.846 Kp |
| 80% range coverage | 80.8% |
| Persistence baseline RMSE | 0.862 Kp |

**Inputs:** IMF |B|, Bx, By, Bz (GSM), proton speed, density, temperature and F10.7 solar flux. **No geomagnetic
indices are used as inputs**, so the nowcast does not wait for magnetometer data.

**Limitations:** the largest storms are under-predicted (about −0.6 Kp for G3+), and sudden onsets show up
1–2 h late within a 3-hour Kp block.

**Data:** NASA/GSFC OMNIWeb (training features), GFZ Potsdam Kp (labels, CC BY 4.0), NOAA SWPC (live inputs).
Code: [github.com/Syeda-Aliza-Ayaz/Tormenta](https://github.com/Syeda-Aliza-Ayaz/Tormenta)
""")
