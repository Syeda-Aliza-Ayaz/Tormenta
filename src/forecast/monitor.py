"""Forecaster health check: retrain only when performance drops (PLAN.md §9, DECISIONS D-12, D-53).

Weekly, from the live scores (forecasts/scores.csv):
  skill   the headline model's skill against the 27-day average over the last WINDOW_DAYS (56) target days,
          lead days 1–3, on exactly the same forecasts (skill vs a reference is stable through storms; raw error
          is not)
  floor   the 5th percentile of that same 56-day skill over the test period (2020 → mid-2026): how low it gets
          about one window in twenty while the model is fine
  status  insufficient_data (too few scored pairs) · healthy · degraded (skill < floor)

A retrain happens only after CONSECUTIVE degraded checks. The candidate is trained up to the start of a 6-month
holdout of the newest definitive data; both models are scored on that holdout and the candidate replaces the
incumbent only if its Ap RMSE ≤ incumbent × GATE_TOLERANCE. Every check and retrain is recorded in
forecasts/monitor.json.

    python -m src.forecast.monitor            # check only
    python -m src.forecast.monitor --act      # check, and retrain if the rule says so
"""
import argparse
import json

import numpy as np
import pandas as pd

from src import backtest, config
from src.forecast import gbm, storm

HEADLINE, REFERENCE = "histgb", "trailing27"
WINDOW_DAYS = 56           # 28-day skill is too noisy: below 0 in 37% of test windows (D-53)
LEADS = (1, 2, 3)
MIN_PAIRS = 120             # scored (origin, lead) pairs needed before a window counts (~40 issue days)
CONSECUTIVE = 2
FLOOR_QUANTILE = 0.05
STATE = config.FORECASTS_DIR / "monitor.json"
KEY = ["origin", "lead", "target_date"]


def window_skill(scored: pd.DataFrame, end: pd.Timestamp) -> tuple:
    """(skill, pairs) of HEADLINE vs REFERENCE on target days in (end − WINDOW_DAYS, end], lead days 1–3."""
    w = scored[scored["target_date"].between(end - pd.Timedelta(days=WINDOW_DAYS - 1), end)
               & scored["lead"].isin(LEADS) & scored["ap_obs"].notna()]
    h = w[w["model"] == HEADLINE][KEY + ["ap", "ap_obs"]]
    r = w[w["model"] == REFERENCE][KEY + ["ap"]]
    both = h.merge(r, on=KEY, suffixes=("", "_ref"))
    if len(both) < MIN_PAIRS:
        return np.nan, len(both)
    mse = np.mean((both["ap"] - both["ap_obs"]) ** 2)
    mse_ref = np.mean((both["ap_ref"] - both["ap_obs"]) ** 2)
    return float(1 - mse / mse_ref) if mse_ref > 0 else np.nan, len(both)


def test_windows() -> pd.DataFrame:
    """The monitor's skill on the test period, one window ending every 7 days (what it would have seen)."""
    fc = pd.read_csv(config.FORECAST_REPORTS_DIR / "test_forecasts.csv.gz", parse_dates=["origin", "target_date"])
    ends = pd.date_range(fc["target_date"].min() + pd.Timedelta(days=WINDOW_DAYS), fc["target_date"].max(), freq="7D")
    return pd.DataFrame([{"window_end": e, "skill": window_skill(fc, e)[0]} for e in ends])


def floor_from_test() -> float:
    """5th percentile of the window skill over the test period."""
    return float(np.nanquantile(test_windows()["skill"], FLOOR_QUANTILE))


def load_state(path=None) -> dict:
    path = path or STATE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"floor": None, "checks": [], "retrains": []}


def save_state(state: dict, path=None):
    path = path or STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def check(scored: pd.DataFrame, today: pd.Timestamp, state: dict) -> dict:
    """Append one weekly check to the state and say whether a retrain is due."""
    if state.get("floor") is None:
        state["floor"] = floor_from_test()
    end = scored.loc[scored["ap_obs"].notna(), "target_date"].max() if len(scored) else today
    skill, pairs = window_skill(scored, end) if len(scored) else (np.nan, 0)
    if np.isnan(skill):
        status = "insufficient_data"
    else:
        status = "healthy" if skill >= state["floor"] else "degraded"
    entry = {"checked_on": str(today.date()), "window_end": str(pd.Timestamp(end).date()),
             "skill": None if np.isnan(skill) else round(skill, 4), "pairs": int(pairs),
             "floor": round(state["floor"], 4), "status": status}
    state["checks"].append(entry)
    recent = [c["status"] for c in state["checks"][-CONSECUTIVE:]]
    entry["retrain_due"] = len(recent) == CONSECUTIVE and all(s == "degraded" for s in recent)
    return entry


def retrain(daily: pd.DataFrame, state: dict, today: pd.Timestamp) -> dict:
    """Candidate trained up to a 6-month holdout of the newest definitive data; promoted only if no worse there."""
    params, log_ap = gbm.load_params()
    definitive = backtest.training_rows(daily, pd.Timestamp(daily.index[daily["definitive"]].max()) + pd.Timedelta(days=1))
    hold_start = definitive.index.max() - pd.DateOffset(months=config.GATE_HOLDOUT_MONTHS)
    candidate = gbm.HistGBDirect(params, log_ap=log_ap).fit(definitive.loc[: hold_start - pd.Timedelta(days=1)])
    incumbent = gbm.HistGBDirect.load()
    assert pd.Timestamp(incumbent.trained_until_) < hold_start, "incumbent was trained on the holdout"

    origins = backtest.origins_for(hold_start, definitive.index.max())
    rmse = {}
    for name, model in (("candidate", candidate), ("incumbent", incumbent)):
        fc = backtest.attach_actuals(model.predict(daily, origins), daily)
        fc = fc[fc["target_date"].between(hold_start, definitive.index.max()) & fc["obs_definitive"]]
        rmse[name] = float(np.sqrt(np.mean((fc["ap"] - fc["ap_obs"]) ** 2)))
    promote = rmse["candidate"] <= rmse["incumbent"] * config.GATE_TOLERANCE
    record = {"date": str(today.date()), "holdout_start": str(hold_start.date()), **{f"{k}_rmse": round(v, 4)
              for k, v in rmse.items()}, "promoted": bool(promote), "trained_until": candidate.trained_until_}
    if promote:
        candidate.save(reason="monitor: degraded twice", holdout_rmse=rmse["candidate"])
        warn = storm.StormClassifier.load()
        refit = storm.StormClassifier().fit(definitive.loc[: hold_start - pd.Timedelta(days=1)])
        refit.thresholds_ = warn.thresholds_
        refit.save(thresholds=warn.thresholds_)
    state["retrains"].append(record)
    return record


def main(act: bool = False) -> dict:
    from src.daily import load_daily
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    scored = (pd.read_csv(config.FORECAST_SCORES, parse_dates=["origin", "target_date"])
              if config.FORECAST_SCORES.exists() else pd.DataFrame())
    state = load_state()
    entry = check(scored, today, state)
    print(f"forecaster health: {entry['status']} (skill {entry['skill']}, {entry['pairs']} pairs, "
          f"floor {entry['floor']}) -> retrain {'due' if entry['retrain_due'] else 'not needed'}")
    if entry["retrain_due"] and act:
        record = retrain(load_daily(), state, today)
        print(f"retrain: candidate {record['candidate_rmse']} vs incumbent {record['incumbent_rmse']} "
              f"-> {'promoted' if record['promoted'] else 'kept incumbent'}")
    save_state(state)
    return entry


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--act", action="store_true", help="retrain when two consecutive checks are degraded")
    from src.forecast import monitor as _module      # pickle saved models under src.forecast.*, not __main__
    _module.main(act=ap.parse_args().act)
