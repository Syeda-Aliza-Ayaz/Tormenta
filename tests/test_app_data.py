"""Files behind the app's "Try the forecaster" panel: out-of-sample only, complete, and the history it needs."""
import pandas as pd
import pytest

from src import config
from src.forecast import app_data


@pytest.fixture(scope="module")
def past():
    if not config.PAST_FORECASTS.exists():
        pytest.skip("no past_forecasts file")
    return pd.read_csv(config.PAST_FORECASTS, parse_dates=["origin", "target_date"])


def test_past_forecasts_are_out_of_sample_and_complete(past):
    assert past["target_date"].min() >= pd.Timestamp(f"{config.TEST_START_YEAR}-01-01")   # never training years
    assert set(past["model"]) >= set(app_data.MODELS) | {"storm_warning"}
    per_origin = past[past["model"] == "histgb"].groupby("origin")["lead"].nunique()
    assert (per_origin.iloc[7:-7] == len(config.FORECAST_LEADS)).all()
    assert past.loc[past["model"] == "storm_warning", "storm_prob"].between(0, 1).all()


def test_recent_history_is_long_enough_for_interactive_forecasts():
    recent = pd.read_csv(config.FORECAST_RECENT, index_col="date", parse_dates=["date"])
    assert {"ap", "kpmax", "f107_obs"} <= set(recent.columns)
    assert len(recent) >= 150 and recent.index.is_monotonic_increasing
