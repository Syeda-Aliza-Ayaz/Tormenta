"""The portable (numpy) model used by the browser app must predict exactly like the scikit-learn model."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.portable import load_portable, save_portable
from src.predict import load_bundle, predict_steady, predict_with_interval

pytestmark = pytest.mark.skipif(not config.CURRENT_MODEL.exists(), reason="needs models/current.joblib")


@pytest.fixture(scope="module")
def bundles(tmp_path_factory):
    bundle = load_bundle()
    path = save_portable(bundle, tmp_path_factory.mktemp("portable") / "m.npz")
    return bundle, load_portable(path)


def test_identical_predictions_with_missing_values(bundles):
    bundle, portable = bundles
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(500, len(bundle["features"]))) * 50, columns=bundle["features"])
    X = X.mask(rng.random(X.shape) < 0.15)                   # 15% NaN: exercises missing-value routing
    for m in ("point", "q_lo", "q_hi"):
        np.testing.assert_array_equal(bundle[m].predict(X), portable[m].predict(X))
    pd.testing.assert_frame_equal(predict_with_interval(bundle, X), predict_with_interval(portable, X))


def test_metadata_and_manual_path(bundles):
    bundle, portable = bundles
    assert portable["features"] == bundle["features"]
    assert portable["interval_margin"] == bundle["interval_margin"]
    storm = {"b_scalar": 20, "bx": 3, "by_gsm": 5, "bz_gsm": -15, "speed": 600, "density": 10,
             "temperature": 2e5, "f107": 150}
    assert predict_steady(bundle, storm, "2026-11-01 12:00") == predict_steady(portable, storm, "2026-11-01 12:00")


def test_numpy_metrics_match_sklearn():
    """src.scoring (used by the browser app, no scikit-learn) must agree with sklearn.metrics."""
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    from src.scoring import metrics

    rng = np.random.default_rng(1)
    y, p = rng.uniform(0, 9, 2000), rng.uniform(0, 9, 2000)
    m = metrics(y, p)
    storm = y >= config.STORM_THRESHOLD
    assert np.isclose(m["rmse"], mean_squared_error(y, p) ** 0.5)
    assert np.isclose(m["mae"], mean_absolute_error(y, p)) and np.isclose(m["r2"], r2_score(y, p))
    assert np.isclose(m["storm_rmse"], mean_squared_error(y[storm], p[storm]) ** 0.5)
