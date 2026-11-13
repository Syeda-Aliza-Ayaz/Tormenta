"""Chronos (pretrained transformer): optional dependency, zero-shot, no future data, never pickles its network."""
import pickle

import numpy as np
import pandas as pd
import pytest

from src import config
from src.forecast import chronos_model, registry


def test_registry_leaves_chronos_out_when_torch_is_missing(monkeypatch):
    monkeypatch.setattr(chronos_model, "available", lambda: False)
    assert "chronos" not in [m.name for m in registry.all_models()]
    assert "chronos" not in [m.name for m in registry.production_models()]


def test_live_needs_both_the_marker_and_the_packages(tmp_path, monkeypatch):
    monkeypatch.setattr(chronos_model, "MARKER", tmp_path / "chronos.json")
    monkeypatch.setattr(chronos_model, "available", lambda: True)
    assert not chronos_model.live()
    (tmp_path / "chronos.json").write_text("{}")
    assert chronos_model.live()
    monkeypatch.setattr(chronos_model, "available", lambda: False)
    assert not chronos_model.live()


def test_pickling_drops_the_network():
    m = chronos_model.ChronosForecaster()
    m._pipeline = object()
    assert pickle.loads(pickle.dumps(m))._pipeline is None


@pytest.mark.skipif(not chronos_model.available(), reason="torch / chronos-forecasting not installed")
def test_forecasts_use_only_the_context_up_to_each_origin():
    rng = np.random.default_rng(6)
    idx = pd.date_range("2015-01-01", "2016-12-31", freq="D", name="date")
    ap = np.clip(10 + 6 * np.sin(2 * np.pi * np.arange(len(idx)) / 27) + rng.gamma(2, 2, len(idx)), 0, 400)
    daily = pd.DataFrame({"ap": ap, "kpmax": np.clip(1 + ap / 8, 0, 9), "f107_obs": 120.0, "gfz_flag": 2,
                          "definitive": True}, index=idx)
    m = chronos_model.ChronosForecaster()
    origins = pd.DatetimeIndex(["2016-03-01", "2016-09-15"])
    full = m.predict(daily, origins)
    for o in origins:
        cut = m.predict(daily.loc[:o], [o])
        pd.testing.assert_frame_equal(full[full["origin"] == o].reset_index(drop=True), cut, atol=1e-4)
    assert full["ap"].between(0, 400).all() and full["kpmax"].between(0, 9).all()
    assert len(full) == len(origins) * len(config.FORECAST_LEADS)
