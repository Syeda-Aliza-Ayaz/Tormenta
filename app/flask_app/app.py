"""Tormenta Flask app: HTML form + JSON API on localhost.

Run from the project folder:   .venv\\Scripts\\python app\\flask_app\\app.py   →  http://127.0.0.1:5000

Routes
  GET  /            form (manual input) + "Use live data" button
  POST /            form submit → Kp for the entered values (assumed steady for 3 days)
  GET  /live        live nowcast from NOAA SWPC; also fills the form with the latest hourly values
  POST /predict     JSON API, manual input → {"kp_pred", "kp_lo", "kp_hi", "level", ...}
  GET  /api/live    JSON API, live nowcast (cached for 5 minutes)
  GET  /forecast    7-day forecast page (latest daily issue, all models, 80% ranges, storm risk)
  GET  /api/forecast  JSON API, the same
  GET  /health      model version / liveness
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from flask import Flask, jsonify, render_template, request  # noqa: E402

from src import config  # noqa: E402
from src.ingest import fetch_live  # noqa: E402
from src.predict import (INPUT_LIMITS, load_bundle, nowcast, predict_steady, storm_level,  # noqa: E402
                         validate_inputs)

LIVE_CACHE_SECONDS = 300
ASSUMPTION = "Manual inputs are assumed to have held steady for the past 3 days (the model also uses lags and 24-h averages)."

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
BUNDLE = load_bundle()
_live_cache = {"at": 0.0, "pred": None, "hourly": None, "f107": None}


def _row(t, r) -> dict:
    return {"time": f"{t:%Y-%m-%d %H:00} UTC", "kp_pred": round(float(r["kp_pred"]), 2),
            "kp_lo": round(float(r["kp_lo"]), 2), "kp_hi": round(float(r["kp_hi"]), 2),
            "level": storm_level(r["kp_pred"])}


def live_data() -> dict:
    """Live nowcast summary, refreshed at most every LIVE_CACHE_SECONDS (SWPC updates every minute)."""
    if _live_cache["pred"] is None or time.time() - _live_cache["at"] > LIVE_CACHE_SECONDS:
        pred, hourly = nowcast(BUNDLE)
        _live_cache.update(at=time.time(), pred=pred, hourly=hourly, f107=fetch_live.fetch_f107())
    pred = _live_cache["pred"]
    past, ahead = pred[~pred["ahead"]], pred[pred["ahead"]]
    return {
        "now": _row(past.index[-1], past.iloc[-1]),
        "ahead": _row(ahead.index[-1], ahead.iloc[-1]) if len(ahead) else None,
        "last_24h": [_row(t, r) for t, r in past.tail(24).iterrows()],
        "model": BUNDLE["version"],
    }


def live_form_values() -> dict:
    """Latest complete hourly inputs + latest F10.7, to pre-fill the form."""
    hourly = _live_cache["hourly"].dropna()
    latest = hourly.iloc[-1]
    values = {c: f"{latest[c]:.4g}" for c in hourly.columns}
    values["f107"] = f"{_live_cache['f107'].dropna().iloc[-1]:.4g}"
    return values


@app.get("/")
def index():
    return render_template("index.html", fields=INPUT_LIMITS, values={}, errors={}, result=None, live=None,
                           live_error=None, assumption=ASSUMPTION, model=BUNDLE["version"])


@app.post("/")
def submit_form():
    values, errors = validate_inputs(request.form)
    result = None if errors else predict_steady(BUNDLE, values)
    return render_template("index.html", fields=INPUT_LIMITS, values=request.form, errors=errors, result=result,
                           live=None, live_error=None, assumption=ASSUMPTION,
                           model=BUNDLE["version"]), 400 if errors else 200


@app.get("/live")
def live_page():
    try:
        live, values, error = live_data(), live_form_values(), None
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        live, values, error = None, {}, f"Could not get live data from NOAA SWPC ({type(exc).__name__}). Try again in a minute."
    return render_template("index.html", fields=INPUT_LIMITS, values=values, errors={}, result=None, live=live,
                           live_error=error, assumption=ASSUMPTION, model=BUNDLE["version"]), 503 if error else 200


@app.post("/predict")
def api_predict():
    payload = request.get_json(silent=True)
    payload = request.form if payload is None else payload
    if not hasattr(payload, "get"):
        return jsonify(error="Send a JSON object with the input fields."), 400
    values, errors = validate_inputs(payload)
    if errors:
        return jsonify(error="Invalid input.", fields=errors,
                       expected={k: {"min": lo, "max": hi, "label": label}
                                 for k, (lo, hi, label) in INPUT_LIMITS.items()}), 400
    return jsonify(**predict_steady(BUNDLE, values), assumption=ASSUMPTION, model=BUNDLE["version"])


@app.get("/api/live")
def api_live():
    try:
        return jsonify(live_data())
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        return jsonify(error=f"Live data unavailable from NOAA SWPC ({type(exc).__name__})."), 503


@app.get("/health")
def health():
    return jsonify(status="ok", model=BUNDLE["version"], trained_until=BUNDLE["trained_until"])


# ── 7-day forecast (read from the daily job's files; no model is run here) ─────
FORECAST_NAMES = {"histgb": "HistGB (headline)", "arimax": "ARIMAX", "trailing27": "27-day average",
                  "persistence": "Persistence", "recurrence27": "27-day recurrence", "climatology": "Climatology"}


def latest_forecast() -> dict:
    """The newest issue in forecasts/log.csv (all models, with 80% ranges) and its storm risk."""
    log = pd.read_csv(config.FORECAST_LOG, parse_dates=["issued_at", "origin", "target_date"])
    if not len(log):
        raise ValueError("no forecast issued yet")
    origin = log["origin"].max()
    latest = log[log["origin"] == origin].sort_values(["model", "lead"])
    models = {}
    for name, g in latest.groupby("model"):
        models[name] = [{"date": f"{r.target_date:%Y-%m-%d}", "lead": int(r.lead),
                         **{k: (None if pd.isna(getattr(r, k)) else round(float(getattr(r, k)), 2))
                            for k in ("ap", "ap_lo", "ap_hi", "kpmax", "kpmax_lo", "kpmax_hi")}}
                        for r in g.itertuples()]
    storm = []
    if config.STORM_LOG.exists():
        s = pd.read_csv(config.STORM_LOG, parse_dates=["origin", "target_date"])
        s = s[s["origin"] == origin].sort_values("lead")
        storm = [{"date": f"{r.target_date:%Y-%m-%d}", "storm_prob": round(float(r.storm_prob), 3),
                  "warning": str(r.warning) == "True"} for r in s.itertuples()]
    return {"origin": f"{origin:%Y-%m-%d}", "issued_at": f"{latest['issued_at'].max():%Y-%m-%d %H:%M} UTC",
            "headline": "histgb", "models": models, "storm": storm}


@app.get("/forecast")
def forecast_page():
    try:
        fc, error = latest_forecast(), None
    except (FileNotFoundError, ValueError) as exc:
        fc, error = None, f"No forecast available ({exc})."
    return render_template("forecast.html", fc=fc, error=error, names=FORECAST_NAMES), 503 if error else 200


@app.get("/api/forecast")
def api_forecast():
    try:
        return jsonify(latest_forecast())
    except (FileNotFoundError, ValueError) as exc:
        return jsonify(error=f"No forecast available ({exc})."), 503


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="Not found.", routes=["/", "/live", "/predict", "/api/live", "/forecast", "/api/forecast",
                                              "/health"]), 404


@app.errorhandler(405)
def wrong_method(_):
    return jsonify(error="Method not allowed. /predict expects POST with JSON."), 405


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
