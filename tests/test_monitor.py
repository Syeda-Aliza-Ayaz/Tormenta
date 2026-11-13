"""Retrain only when performance drops (D-53): the forecaster monitor and the nowcaster health check."""
import numpy as np
import pandas as pd
import pytest

from src.forecast import monitor as M


def _scores(skill_gap: float, days: int = 80, end: str = "2027-01-31") -> pd.DataFrame:
    """Scored live forecasts where HistGB's squared error is (1 − skill_gap) × the 27-day average's."""
    rng = np.random.default_rng(9)
    rows = []
    for origin in pd.date_range(end=pd.Timestamp(end) - pd.Timedelta(days=1), periods=days):
        for lead in M.LEADS:
            obs = rng.uniform(5, 30)
            err = rng.choice([-1, 1]) * 4.0
            rows.append({"model": "trailing27", "origin": origin, "lead": lead,
                         "target_date": origin + pd.Timedelta(days=lead), "ap": obs + err, "ap_obs": obs})
            rows.append({"model": "histgb", "origin": origin, "lead": lead,
                         "target_date": origin + pd.Timedelta(days=lead),
                         "ap": obs + err * np.sqrt(1 - skill_gap), "ap_obs": obs})
    return pd.DataFrame(rows)


def test_window_skill_measures_the_gap():
    skill, pairs = M.window_skill(_scores(0.3), pd.Timestamp("2027-01-31"))
    assert skill == pytest.approx(0.3, abs=1e-9) and pairs >= M.MIN_PAIRS


def test_too_few_pairs_is_insufficient_data():
    state = {"floor": -0.25, "checks": [], "retrains": []}
    entry = M.check(_scores(0.3, days=10), pd.Timestamp("2027-02-01"), state)
    assert entry["status"] == "insufficient_data" and not entry["retrain_due"]


def test_retrain_only_after_two_degraded_checks_in_a_row():
    state = {"floor": -0.25, "checks": [], "retrains": []}
    bad, good = _scores(-0.5), _scores(0.2)                       # skill −0.5 is below the floor
    first = M.check(bad, pd.Timestamp("2027-02-01"), state)
    assert first["status"] == "degraded" and not first["retrain_due"]
    healthy = M.check(good, pd.Timestamp("2027-02-08"), state)
    assert healthy["status"] == "healthy" and not healthy["retrain_due"]
    M.check(bad, pd.Timestamp("2027-02-15"), state)
    second = M.check(bad, pd.Timestamp("2027-02-22"), state)
    assert second["retrain_due"] and len(state["checks"]) == 4


def test_state_roundtrip(tmp_path):
    state = {"floor": -0.2, "checks": [{"status": "healthy"}], "retrains": []}
    M.save_state(state, tmp_path / "m.json")
    assert M.load_state(tmp_path / "m.json") == state


def test_healthy_nowcaster_is_not_retrained(monkeypatch):
    from src import config, update
    if not (config.PROCESSED_CSV.exists() and config.CURRENT_MODEL.exists()):
        pytest.skip("needs the local processed table and current model")
    monkeypatch.setattr(update, "refresh_data", lambda write_f107=True: None)
    # pretend new data arrived after the model was trained, so the health check runs
    real_load = update.load_bundle

    def older_bundle():
        b = dict(real_load())
        b["trained_until"] = "2020-01-01 00:00:00"
        return b
    monkeypatch.setattr(update, "load_bundle", older_bundle)
    monkeypatch.setattr(update, "nowcaster_health", lambda *a: {"skill": 0.6, "reference": 0.56, "floor": 0.46,
                                                                "status": "healthy"})
    monkeypatch.setattr(update.train, "fit_production", lambda *a, **k: pytest.fail("must not retrain"))
    assert update.run(dry_run=True)["status"] == "healthy_no_retrain"
