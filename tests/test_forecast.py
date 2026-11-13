"""v2 forecaster guards: the daily table, the forecaster contract (no future data), and the scorecards."""
import numpy as np
import pandas as pd
import pytest

from src import backtest, config, scorecard
from src.daily import build_daily, check
from src.forecast import registry
from src.forecast.base import COLUMNS


@pytest.fixture
def daily():
    """Synthetic daily table with a 27-day cycle, so recurrence has something to find."""
    rng = np.random.default_rng(1)
    idx = pd.date_range("2010-01-01", "2013-12-31", freq="D", name="date")
    phase = np.sin(2 * np.pi * np.arange(len(idx)) / config.RECURRENCE_DAYS)
    ap = np.clip(12 + 8 * phase + rng.gamma(2, 3, len(idx)), 0, 400).round()
    return pd.DataFrame({"ap": ap, "kpmax": np.clip(1 + ap / 8, 0, 9),
                         "f107_obs": rng.uniform(70, 200, len(idx)), "gfz_flag": 2, "definitive": True},
                        index=idx)


def _gfz(days, **overrides):
    base = {**{f"kp{i}": 2.0 for i in range(1, 9)}, "ap_daily": 7.0, "f107_obs": 150.0,
            "gfz_flag": 2, "definitive": True}
    return pd.DataFrame({**base, **overrides}, index=days)


def test_build_daily_fills_grid_and_takes_max():
    days = pd.date_range("2020-01-01", periods=5, freq="D")
    gfz = _gfz(days).drop(days[2])                      # a missing day
    gfz.loc[days[1], "kp7"] = 5.333
    gfz.loc[days[3], "kp4"] = np.nan                    # an incomplete day has no reliable maximum
    out = build_daily(gfz)
    check(out)
    assert len(out) == 5 and out.loc[days[2]].isna()[["ap", "kpmax"]].all()
    assert not out.loc[days[2], "definitive"]
    assert out.loc[days[1], "kpmax"] == 5.333 and np.isnan(out.loc[days[3], "kpmax"])


def test_check_rejects_definitive_after_open_day():
    days = pd.date_range("2020-01-01", periods=4, freq="D")
    out = build_daily(_gfz(days, definitive=[True, False, True, True], gfz_flag=[2, 1, 2, 2]))
    with pytest.raises(AssertionError, match="definitive day after"):
        check(out)


@pytest.mark.parametrize("model", registry.all_models(), ids=lambda m: m.name)
def test_forecaster_contract_and_causality(model, daily):
    """Shape, leads, target dates — and forecasts for origin D must not change when days after D are removed."""
    model.fit(daily.loc[:"2011-12-31"])
    origins = pd.DatetimeIndex(["2012-03-01", "2012-07-15", "2013-06-30"])
    full = model.predict(daily, origins)
    assert list(full.columns) == COLUMNS
    assert len(full) == len(origins) * len(config.FORECAST_LEADS)
    assert (full["target_date"] - full["origin"]).dt.days.tolist() == full["lead"].tolist()
    assert full[config.FORECAST_TARGETS].notna().all().all()
    for origin in origins:
        cut = model.predict(daily.loc[:origin], [origin])
        pd.testing.assert_frame_equal(full[full["origin"] == origin].reset_index(drop=True), cut)


def test_baseline_values(daily):
    origin = pd.Timestamp("2012-05-10")
    fc = {m.name: m.fit(daily).predict(daily, [origin]).set_index("lead") for m in registry.baselines()}
    assert (fc["persistence"]["ap"] == daily.loc[origin, "ap"]).all()
    for h in config.FORECAST_LEADS:
        assert fc["recurrence27"].loc[h, "ap"] == daily.loc[origin + pd.Timedelta(days=h - 27), "ap"]
    assert fc["trailing27"].loc[1, "ap"] == pytest.approx(daily.loc[:origin, "ap"].iloc[-27:].mean())


def test_backtest_uses_only_past_training_rows_and_scores_every_lead(daily):
    first, last = pd.Timestamp("2013-01-01"), pd.Timestamp("2013-03-31")
    assert backtest.training_rows(daily, first).index.max() < first
    fc = backtest.run(registry.baselines(), daily, first, last)
    assert fc["target_date"].between(first, last).all()
    per_lead = fc.groupby(["model", "lead"]).size()
    assert (per_lead == (last - first).days + 1).all()          # every target day, every lead day


def test_skill_score_against_itself_is_zero_and_contingency():
    fc = pd.DataFrame({"model": ["a", "a", "persistence", "persistence"], "origin": pd.Timestamp("2020-01-01"),
                       "lead": [1, 2, 1, 2], "target_date": pd.to_datetime(["2020-01-02", "2020-01-03"] * 2),
                       "ap": [10, 20, 12, 30], "kpmax": [3, 5, 3, 6], "ap_obs": [11, 22, 11, 22],
                       "kpmax_obs": [3, 6, 3, 6]})
    t = scorecard.lead_table(fc, references=("persistence",)).set_index(["model", "target", "lead"])
    assert t.loc[("persistence", "ap", 1), "skill_vs_persistence"] == 0
    assert t.loc[("a", "ap", 2), "skill_vs_persistence"] == pytest.approx(1 - 4 / 64)
    c = scorecard.contingency([True, True, False, False], [True, False, True, False])
    assert (c["hits"], c["false_alarms"], c["misses"], c["correct_negatives"]) == (1, 1, 1, 1)
    assert c["pod"] == 0.5 and c["far"] == 0.5 and c["hss"] == 0


def test_recent_hindcast_stays_outside_validation_and_test(daily):
    """'recent' starts the day after the last definitive day (end of the test period) and scores provisional days."""
    d = daily.copy()
    d.loc["2013-07-01":, "definitive"] = False                 # provisional tail, as in the live GFZ file
    d.loc["2013-07-01":, "gfz_flag"] = 1
    first, last = backtest.period("recent", d)
    assert first == pd.Timestamp("2013-07-01") and last == d.index.max()
    assert first > backtest.period("test", d)[1]
    fc = backtest.hindcast(d, first, last)
    assert len(fc) and fc["target_date"].min() >= first and not fc["obs_definitive"].any()
    assert set(fc["model"]) == {m.name for m in registry.production_models()}
