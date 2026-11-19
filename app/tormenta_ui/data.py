"""Data access for the dashboard: the daily job's files, report metrics, live NOAA data and the models.

Everything here is cached by Streamlit. Nothing imports scikit-learn at module level, so the in-browser build (stlite)
can load this file; the forecast models are imported lazily and are simply unavailable there.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config, scoring  # noqa: E402
from src.ingest import fetch_live  # noqa: E402
from src.predict import load_bundle, nowcast  # noqa: E402

IN_BROWSER = sys.platform == "emscripten"           # Hugging Face static Space: stlite (Streamlit on Pyodide)
NETWORK_ERRORS = (requests.RequestException,)
if IN_BROWSER:
    from pyodide.ffi import JsException             # browser fetch failures surface as JS exceptions
    NETWORK_ERRORS += (JsException,)
LIVE_ERRORS = NETWORK_ERRORS + (ValueError, KeyError, IndexError)

# ── Storm levels (NOAA scale) ────────────────────────────────────────────────
_B = config.KP_BINS        # level edges used everywhere in the project: 0, 3.5, 4.5, 5.5, 6.5, 9.01
LEVELS = [  # (lower Kp, upper Kp, short, name, ramp index, what it means)
    (_B[0], 3.0, "Quiet", "Quiet", 0, "Aurora only near the poles; no effect on technology."),
    (3.0, _B[1], "Unsettled", "Unsettled", 1, "Slightly disturbed field. Aurora only near the poles."),
    (_B[1], _B[2], "Active", "Active", 2,
     "Aurora possible at high latitudes (northern Scandinavia, Alaska, northern Canada)."),
    (_B[2], _B[3], "G1", "Minor storm", 3,
     "Weak power-grid fluctuations possible; aurora visible around 60° geomagnetic latitude."),
    (_B[3], _B[4], "G2", "Moderate storm", 4,
     "High-latitude power systems may see voltage alarms; aurora down to about 55°."),
    (_B[4], 7.5, "G3", "Strong storm", 5,
     "Satellites, GPS and HF radio can be disrupted; aurora down to about 50°."),
    (7.5, _B[5], "G4+", "Severe to extreme storm", 6,
     "Widespread power-grid and satellite problems possible; aurora can reach mid-latitudes."),
]


def level_of(kp: float):
    kp = round(float(kp), 1)                         # level of the number shown on screen
    return next(lv for lv in LEVELS if kp < lv[1] or lv is LEVELS[-1])


def scene_level(kp: float) -> str:
    """Aurora intensity for the hero: quiet, unsettled or storm."""
    return "quiet" if kp < 3 else ("unsettled" if kp < config.STORM_THRESHOLD else "storm")


# ── Forecast series ──────────────────────────────────────────────────────────
FC_SERIES = {"histgb": "HistGB", "arimax": "ARIMAX", "arima": "ARIMA", "sarima": "SARIMA",
             "noaa": "NOAA official", "trailing27": "27-day average", "persistence": "Persistence",
             "recurrence27": "27-day recurrence", "climatology": "Climatology", "chronos": "Chronos"}
FC_TRAINED = {"histgb", "arima", "sarima", "arimax"}
FC_REFERENCE = {"trailing27", "persistence", "recurrence27", "climatology"}
FC_TARGETS = {"Max Kp": ("kpmax", "max Kp"), "Ap": ("ap", "Ap")}
GFZ_FLAGS = {0: "nowcast", 1: "provisional", 2: "definitive"}
HISTORY_DAYS = 30
EDIT_DAYS = 10            # days the user can edit in Explore; the forecast also uses ~120 earlier days
CONTEXT_DAYS = 150
NO_NOAA = pd.DataFrame(columns=["product", "issued", "origin", "lead", "target_date", "f107", "ap", "kpmax"])

# ── Nowcast what-if ──────────────────────────────────────────────────────────
DEFAULTS = {"b_scalar": 5.0, "bx": 1.0, "by_gsm": 2.0, "bz_gsm": 0.0, "speed": 400.0, "density": 5.0,
            "temperature": 100000.0, "f107": 120.0}
PRESETS = {
    "Quiet day": DEFAULTS,
    "Fast solar wind": {**DEFAULTS, "b_scalar": 8.0, "bz_gsm": -4.0, "speed": 650.0, "density": 3.0,
                        "temperature": 250000.0},
    "CME arrival": {"b_scalar": 20.0, "bx": 3.0, "by_gsm": 5.0, "bz_gsm": -15.0, "speed": 600.0,
                    "density": 10.0, "temperature": 200000.0, "f107": 150.0},
    "May 2024 superstorm": {"b_scalar": 70.0, "bx": 3.0, "by_gsm": 20.0, "bz_gsm": -45.0, "speed": 800.0,
                            "density": 30.0, "temperature": 600000.0, "f107": 200.0},
}
STEPS = {"speed": 10.0, "temperature": 10000.0, "f107": 1.0}
SWEEPS = {"Bz (nT)": ("bz_gsm", np.arange(-40, 15.1, 2.5)), "Speed (km/s)": ("speed", np.arange(300, 1001, 50)),
          "Density (cm⁻³)": ("density", np.arange(1, 41, 2))}
HISTORY_OPTIONS = ["Real (live data up to now)", "Steady at these values"]

# ── Explore presets ──────────────────────────────────────────────────────────
TRY_PRESETS = {
    "Latest real data": None,
    "Quiet week": {"days": range(-6, 1), "ap": 4.0, "kpmax": 1.7},
    "Storm now": {"days": range(-1, 1), "ap": 80.0, "kpmax": 7.0},
    "Storm 27 days ago": {"days": range(-27, -24), "ap": 60.0, "kpmax": 6.0},
}
NOTABLE_DAYS = {"8 May 2024 · before the superstorm": "2024-05-08"}

# ── Scorecard ────────────────────────────────────────────────────────────────
SC_PERIODS = {"Test 2020 – Jun 2026": "test", "Validation 2017–19": "validation", "Recent days": "recent"}
SC_STATUS = {"histgb": "live", "arimax": "live2", "noaa": "bench", "arima": "off", "sarima": "off", "chronos": "off",
             "trailing27": "ref", "persistence": "ref", "recurrence27": "ref", "climatology": "ref"}
SC_KIND = {"histgb": "Gradient-boosted trees, 14 direct models", "noaa": "Official forecast, forecasters + solar imagery",
           "arimax": "Linear time series + 27-day recurrence, F10.7", "arima": "Linear time series",
           "sarima": "ARIMA + 27-day season", "chronos": "Pretrained transformer, zero-shot",
           "trailing27": "Mean of the last solar rotation", "climatology": "Average for the calendar month",
           "persistence": "Tomorrow = today", "recurrence27": "Value one solar rotation earlier"}
SC_FIGURES = {"Skill vs lead day": "01_skill_vs_lead.png", "Storm skill vs lead day": "02_storm_skill_vs_lead.png",
              "80% range coverage (test)": "03_interval_coverage_test.png",
              "May 2024 superstorm": "04_may2024_case_study.png"}


@st.cache_data(ttl=600)
def get_forecasts():
    """The daily job's files (src/issue.py): no network call, so this works in the browser Space too."""
    log = pd.read_csv(ROOT / "forecasts" / "log.csv", parse_dates=["issued_at", "origin", "target_date"])
    scores = pd.read_csv(ROOT / "forecasts" / "scores.csv", parse_dates=["issued_at", "origin", "target_date"])
    recent = pd.read_csv(ROOT / "forecasts" / "recent.csv", index_col="date", parse_dates=["date"])
    noaa = pd.read_csv(ROOT / "forecasts" / "noaa_live.csv", parse_dates=["issued", "origin", "target_date"])
    return log, scores, recent, noaa


@st.cache_data(ttl=600)
def get_storm_log() -> pd.DataFrame:
    """Storm risk per lead day (src/forecast/storm.py); empty until the first issue that includes it."""
    try:
        return pd.read_csv(ROOT / "forecasts" / "storm_log.csv", parse_dates=["issued_at", "origin", "target_date"])
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_past_forecasts() -> pd.DataFrame:
    return pd.read_csv(ROOT / "forecasts" / "past_forecasts.csv.gz", parse_dates=["origin", "target_date"])


@st.cache_data(ttl=3600)
def get_monitor_state() -> dict:
    import json
    path = ROOT / "forecasts" / "monitor.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@st.cache_data(ttl=3600)
def get_nowcast_test() -> pd.DataFrame:
    return pd.read_csv(ROOT / "reports" / "metrics" / "test.csv", index_col=0)


def report_path(*parts) -> Path:
    return ROOT.joinpath("reports", "forecast", *parts)


@st.cache_data(ttl=3600)
def read_report(*parts) -> pd.DataFrame:
    path = report_path(*parts)
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@st.cache_resource(show_spinner="Loading the forecast models…")
def get_forecast_models():
    """The live forecast models, loaded once. Needs scikit-learn and statsmodels, so None in the browser Space."""
    try:
        from src.forecast import arima, gbm, intervals, storm
        from src.forecast.baselines import Persistence, Recurrence27, TrailingMean
    except ImportError:
        return None
    models = [Persistence(), Recurrence27(), TrailingMean()]
    if gbm.BUNDLE.exists():
        models.append(gbm.HistGBDirect.load())
    path = arima.BUNDLE_DIR / "arimax.joblib"
    if path.exists():
        models.append(arima.StateSpaceForecaster.load(path))
    warn = storm.StormClassifier.load() if storm.BUNDLE.exists() else None
    return {"models": models, "storm": warn, "intervals": intervals}


def run_forecasters(history: pd.DataFrame, kit: dict):
    """Forecast D+1 … D+7 from an edited daily history (last day = D) with every live model."""
    daily = history.asfreq("D").assign(gfz_flag=0, definitive=False)
    origin = daily.index[-1]
    rows = [m.predict(daily, [origin]).assign(model=m.name) for m in kit["models"]]
    fc = kit["intervals"].apply(pd.concat(rows, ignore_index=True), kit["intervals"].load())
    warn = kit["storm"].predict(daily, [origin]) if kit["storm"] is not None else pd.DataFrame()
    return origin, fc, warn


@st.cache_resource(show_spinner="Loading the nowcast model…")
def get_bundle():
    # In the browser (Hugging Face static Space via stlite/Pyodide) the scikit-learn pickle cannot be loaded;
    # the same trees are read from the portable .npz instead (identical predictions, see src/portable.py)
    if IN_BROWSER:
        from src.portable import load_portable
        return load_portable(ROOT / "models" / "current_portable.npz")
    return load_bundle()


@st.cache_data(ttl=300, show_spinner="Fetching real-time data from NOAA SWPC…")
def get_live():
    pred, hourly = nowcast(get_bundle())
    live = pred
    comparisons = [(fetch_live.fetch_swpc_kp, "kp_swpc")]
    if not IN_BROWSER:                              # GFZ sends no CORS header, so browsers may not fetch it
        comparisons.insert(0, (fetch_live.fetch_gfz_nowcast, "kp_gfz"))
    for fetch, name in comparisons:
        try:
            live = scoring.attach_block_kp(live, fetch(), name)
        except NETWORK_ERRORS:
            pass                                    # comparison only; the nowcast still works
    return live, hourly, fetch_live.fetch_f107(), pd.Timestamp.now("UTC")


def try_live():
    """get_live(), or None when NOAA cannot be reached (pages degrade instead of failing)."""
    try:
        return get_live()
    except LIVE_ERRORS:
        return None


def latest_issue():
    """(origin, rows of that issue, scores, recent observations, NOAA products) or None before the first issue."""
    try:
        log, scores, recent, noaa = get_forecasts()
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return None
    if not len(log):
        return None
    origin = log["origin"].max()
    return origin, log[log["origin"] == origin], scores, recent, noaa


def noaa_kp_for(noaa: pd.DataFrame, day: pd.Timestamp):
    """NOAA's newest 3-day forecast of max Kp for `day`, or None."""
    rows = noaa[(noaa["product"] == "3day") & (noaa["target_date"] == day)].dropna(subset=["kpmax"])
    return None if not len(rows) else float(rows.sort_values("issued")["kpmax"].iloc[-1])


def comparison_rows(period: str) -> list:
    """One dict per model: day-1/3/7 Ap RMSE and mean skill vs the 27-day average (lead days present)."""
    leads = read_report("metrics", f"{period}_leads.csv")
    if not len(leads):
        return []
    ap = leads[leads["target"] == "ap"]
    rows = []
    for m, g in ap.groupby("model"):
        rmse = g.set_index("lead")["rmse"]
        rows.append({"model": m, "d1": rmse.get(1), "d3": rmse.get(3), "d7": rmse.get(7),
                     "skill": g["skill_vs_trailing27"].mean(), "leads": len(g)})
    return sorted(rows, key=lambda r: -r["skill"])


def storm_table_for(period: str, lead: int) -> pd.DataFrame:
    t = pd.concat([read_report("metrics", f"{period}_storms.csv"),
                   read_report("metrics", f"{period}_storm_warning.csv")], ignore_index=True)
    if not len(t):
        return t
    return t[(t["lead"] == lead) & (t["model"] != "noaa")].sort_values("hss", ascending=False)
