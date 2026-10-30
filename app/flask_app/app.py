"""Tormenta Flask app: HTML form + JSON API on localhost.

Run from the project folder:   .venv\\Scripts\\python app\\flask_app\\app.py   →  http://127.0.0.1:5000

Routes
  GET  /            form (manual input) + "Use live data" button
  POST /            form submit → Kp for the entered values (assumed steady for 3 days)
  GET  /live        live nowcast from NOAA SWPC; also fills the form with the latest hourly values
  POST /predict     JSON API, manual input → {"kp_pred", "kp_lo", "kp_hi", "level", ...}
  GET  /api/live    JSON API, live nowcast (cached for 5 minutes)
  GET  /health      model version / liveness
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from flask import Flask, jsonify, render_template, request  # noqa: E402

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


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="Not found.", routes=["/", "/live", "/predict", "/api/live", "/health"]), 404


@app.errorhandler(405)
def wrong_method(_):
    return jsonify(error="Method not allowed. /predict expects POST with JSON."), 405


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
