"""Flask app: validation, error messages and JSON shapes (live data is mocked, no network)."""
import importlib.util

import pandas as pd
import pytest
import requests

from src import config

pytest.importorskip("flask")
pytestmark = pytest.mark.skipif(not config.CURRENT_MODEL.exists(), reason="needs models/current.joblib")

QUIET = {"b_scalar": 5, "bx": 1, "by_gsm": 2, "bz_gsm": 1, "speed": 380, "density": 5,
         "temperature": 80000, "f107": 120}


@pytest.fixture(scope="module")
def flask_module():
    spec = importlib.util.spec_from_file_location("flask_app", config.ROOT / "app" / "flask_app" / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(flask_module):
    flask_module._live_cache.update(at=0.0, pred=None)
    return flask_module.app.test_client()


def test_health(client):
    assert client.get("/health").get_json()["status"] == "ok"


def test_predict_json_ok(client):
    out = client.post("/predict", json=QUIET).get_json()
    assert 0 <= out["kp_lo"] <= out["kp_pred"] <= out["kp_hi"] <= 9 and out["level"] == "0-3"


def test_storm_inputs_give_storm_level(client):
    storm = {**QUIET, "b_scalar": 40, "bz_gsm": -35, "by_gsm": 10, "speed": 800, "density": 20}
    assert client.post("/predict", json=storm).get_json()["kp_pred"] >= 6


def test_predict_reports_each_bad_field(client):
    resp = client.post("/predict", json={**QUIET, "speed": "fast", "density": -1, "f107": ""})
    body = resp.get_json()
    assert resp.status_code == 400
    assert set(body["fields"]) == {"speed", "density", "f107"}
    assert "number" in body["fields"]["speed"] and "between" in body["fields"]["density"]


def test_inconsistent_field_magnitude_rejected(client):
    resp = client.post("/predict", json={**QUIET, "b_scalar": 1, "bz_gsm": -20})
    assert resp.status_code == 400 and "b_scalar" in resp.get_json()["fields"]


def test_non_object_json_rejected(client):
    assert client.post("/predict", json=[1, 2, 3]).status_code == 400


def test_html_form_shows_errors(client):
    resp = client.post("/", data={**QUIET, "speed": "abc"})
    assert resp.status_code == 400 and b"must be a number" in resp.data


def test_live_unavailable_gives_503(client, flask_module, monkeypatch):
    def offline(_bundle):
        raise requests.ConnectionError("offline")
    monkeypatch.setattr(flask_module, "nowcast", offline)
    assert client.get("/api/live").status_code == 503
    assert b"Could not get live data" in client.get("/live").data


def test_live_json_shape(client, flask_module, monkeypatch):
    idx = pd.date_range("2026-10-30", periods=30, freq="h")
    pred = pd.DataFrame({"kp_pred": 2.0, "kp_lo": 1.0, "kp_hi": 3.0, "ahead": [False] * 29 + [True]}, index=idx)
    hourly = pd.DataFrame({c: 1.0 for c in config.SW_FEATURES}, index=idx)
    monkeypatch.setattr(flask_module, "nowcast", lambda _b: (pred, hourly))
    monkeypatch.setattr(flask_module.fetch_live, "fetch_f107", lambda: pd.Series([100.0], index=idx[:1]))
    body = client.get("/api/live").get_json()
    assert body["now"]["time"].startswith("2026-10-31 04:00") and body["ahead"] is not None
    assert len(body["last_24h"]) == 24
    page = client.get("/live")
    assert page.status_code == 200 and b"Live nowcast" in page.data and b'value="100"' in page.data
