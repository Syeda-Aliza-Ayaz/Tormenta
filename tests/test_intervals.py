"""80% ranges: calibrated from errors, widen with the forecast level, always contain the forecast, reach the log."""
import json

import numpy as np
import pandas as pd
import pytest

from src import config
from src.forecast import intervals as I


@pytest.fixture
def scored():
    """A model whose Ap is off by a log ratio uniform in [−1, 1] and whose max Kp is off by ±1."""
    rng = np.random.default_rng(5)
    n = 2000
    pred = rng.uniform(3, 40, n)
    ap_obs = np.expm1(np.log1p(pred) + rng.uniform(-1, 1, n))
    kp = rng.uniform(1, 6, n)
    return pd.DataFrame({"model": "m", "lead": rng.integers(1, 8, n), "ap": pred, "ap_obs": ap_obs,
                         "kpmax": kp, "kpmax_obs": np.clip(kp + rng.uniform(-1, 1, n), 0, 9)})


def test_calibrated_quantiles_and_coverage(scored):
    table = I.calibrate(scored)
    lo, hi = table["m"]["ap"]["1"]
    assert lo == pytest.approx(-0.8, abs=0.1) and hi == pytest.approx(0.8, abs=0.1)
    cov = I.coverage(I.apply(scored, table))
    assert cov["coverage"].between(0.75, 0.85).all()             # 80% by construction, in sample


def test_ranges_widen_with_level_contain_the_forecast_and_stay_in_bounds(scored):
    table = I.calibrate(scored)
    ex = pd.DataFrame({"model": "m", "lead": [1, 1, 1], "ap": [0.0, 5.0, 50.0], "kpmax": [0.2, 4.0, 8.9]})
    out = I.apply(ex, table)
    widths = (out["ap_hi"] - out["ap_lo"]).to_numpy()
    assert widths[0] < widths[1] < widths[2]                      # log-ratio ranges grow with activity
    for t in config.FORECAST_TARGETS:
        assert (out[f"{t}_lo"] <= out[t]).all() and (out[t] <= out[f"{t}_hi"]).all()
        assert (out[f"{t}_lo"] >= 0).all() and (out[f"{t}_hi"] <= I.TARGET_MAX[t]).all()


def test_unknown_model_gets_no_range(scored):
    out = I.apply(pd.DataFrame({"model": ["other"], "lead": [1], "ap": [9.0], "kpmax": [3.0]}), I.calibrate(scored))
    assert out[["ap_lo", "ap_hi", "kpmax_lo", "kpmax_hi"]].isna().all(axis=None)


def test_committed_table_covers_every_live_model_and_lead():
    from src.forecast import registry
    if not I.INTERVALS_JSON.exists():
        pytest.skip("no intervals.json")
    table = json.loads(I.INTERVALS_JSON.read_text(encoding="utf-8"))
    for model in registry.production_models():
        for t in config.FORECAST_TARGETS:
            assert set(table[model.name][t]) == {str(h) for h in config.FORECAST_LEADS}, (model.name, t)
