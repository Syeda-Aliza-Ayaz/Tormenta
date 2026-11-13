"""What-if on the real history must agree with the live tab when nothing is edited (DECISIONS D-38)."""
import pandas as pd
import pytest

from src import config
from src.predict import (edited_fields, live_form_values, load_bundle, now_hour, predict_hourly,
                         predict_on_history)
from tests.test_features import synthetic  # noqa: F401  (pytest fixture)


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture
def live(synthetic, bundle):  # noqa: F811
    hourly, f107 = synthetic
    now = hourly.index[-1] - pd.Timedelta(hours=1)          # last hour is "ahead", as live
    pred = predict_hourly(bundle, hourly, f107, now=now)
    return pred, hourly, f107


def test_unedited_live_values_equal_the_live_tab(live, bundle):
    pred, hourly, f107 = live
    hour = now_hour(pred)
    assert not pred.loc[hour, "ahead"] and pred.loc[pred.index > hour, "ahead"].all()
    shown = live_form_values(hourly, f107, hour)
    form = {k: round(v, 2) for k, v in shown.items()}           # what the number inputs display
    assert edited_fields(form, shown) == {}                      # display rounding is not an edit
    out = predict_on_history(bundle, hourly, f107, hour, edited_fields(form, shown))
    for k in ("kp_pred", "kp_lo", "kp_hi"):
        assert out[k] == round(float(pred.loc[hour, k]), 2), k


def test_an_edit_changes_only_the_current_hour(live, bundle):
    pred, hourly, f107 = live
    hour = now_hour(pred)
    stormy = predict_on_history(bundle, hourly, f107, hour, {"bz_gsm": -30.0, "speed": 900.0})
    assert stormy["kp_pred"] > pred.loc[hour, "kp_pred"]         # strongly southward Bz + fast wind → higher Kp
    before = hour - pd.Timedelta(hours=1)
    assert predict_on_history(bundle, hourly, f107, before)["kp_pred"] == round(float(pred.loc[before, "kp_pred"]), 2)


def test_f107_override_reaches_the_features(live, bundle):
    pred, hourly, f107 = live
    hour = now_hour(pred)
    low = predict_on_history(bundle, hourly, f107, hour, {"f107": 70.0})
    high = predict_on_history(bundle, hourly, f107, hour, {"f107": 250.0})
    assert low != high


def test_edited_fields_tolerance():
    shown = {"speed": 412.3456, "bz_gsm": -3.2}
    assert edited_fields({"speed": 412.35, "bz_gsm": -3.2}, shown) == {}
    assert edited_fields({"speed": 500.0, "bz_gsm": -3.2}, shown) == {"speed": 500.0}
