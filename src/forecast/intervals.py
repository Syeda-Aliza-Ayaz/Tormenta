"""80% forecast ranges for every model (PLAN.md §6): from each model's own validation errors, per lead day.

For each model, target and lead day, the 10th and 90th percentiles of the validation errors give the range:
  Ap      errors as log ratios, log(1+obs) − log(1+forecast): the range widens on active days, stays ≥ 0, and
          suits Ap's skew (a fixed ±X would be too wide on quiet days and too narrow in storms)
  max Kp  plain differences, obs − forecast, then clipped to 0–9
The same method for every model, so their ranges are comparable. Calibrated on validation (models fitted on train),
so coverage is checked on days it never saw: the recent hindcast now, the test period later (DECISIONS D-45).
Calibration errors come from 2008–2016 (models fitted ≤ 2007) and validation 2017–2019 (fitted ≤ 2016).

    python -m src.forecast.intervals    # validation backtest of the live models → models/forecast/intervals.json
"""
import json

import numpy as np
import pandas as pd

from src import config

INTERVALS_JSON = config.MODELS_DIR / "forecast" / "intervals.json"
LEVEL = 0.8
CAL_START = "2008-01-01"     # calibration: 2008–2016 (inside training, fitted ≤ 2007) + validation 2017–2019
Q_LO, Q_HI = (1 - LEVEL) / 2, 1 - (1 - LEVEL) / 2
TARGET_MAX = {"ap": 400.0, "kpmax": 9.0}


def _error(target: str, obs, pred):
    return np.log1p(obs) - np.log1p(pred) if target == "ap" else obs - pred


def _bounds(target: str, pred, q):
    out = np.expm1(np.log1p(pred) + q) if target == "ap" else pred + q
    return np.clip(out, 0, TARGET_MAX[target])


def calibrate(fc: pd.DataFrame) -> dict:
    """{model: {target: {lead: [q_lo, q_hi]}}} from a scored backtest frame (forecast + *_obs columns)."""
    table = {}
    for (model, lead), g in fc.groupby(["model", "lead"]):
        for t in config.FORECAST_TARGETS:
            ok = g[[t, f"{t}_obs"]].dropna()
            if len(ok) < 30:
                continue
            err = _error(t, ok[f"{t}_obs"].to_numpy(), ok[t].to_numpy())
            table.setdefault(model, {}).setdefault(t, {})[str(int(lead))] = [float(np.quantile(err, Q_LO)),
                                                                              float(np.quantile(err, Q_HI))]
    return table


def apply(fc: pd.DataFrame, table: dict) -> pd.DataFrame:
    """Fill {target}_lo / {target}_hi for every model and lead day the table knows (others stay NaN)."""
    fc = fc.copy()
    for t in config.FORECAST_TARGETS:
        lo, hi = np.full(len(fc), np.nan), np.full(len(fc), np.nan)
        for i, (model, lead, pred) in enumerate(zip(fc["model"], fc["lead"], fc[t])):
            q = table.get(model, {}).get(t, {}).get(str(int(lead)))
            if q is not None and pd.notna(pred):
                lo[i], hi[i] = _bounds(t, pred, q[0]), _bounds(t, pred, q[1])
        fc[f"{t}_lo"] = np.minimum(lo, fc[t])                 # the range always contains the forecast itself
        fc[f"{t}_hi"] = np.maximum(hi, fc[t])
    return fc


def coverage(fc: pd.DataFrame) -> pd.DataFrame:
    """Share of observed values inside the range, and the mean width, per model × target × lead day."""
    rows = []
    for t in config.FORECAST_TARGETS:
        ok = fc.dropna(subset=[t, f"{t}_obs", f"{t}_lo", f"{t}_hi"])
        inside = ok[f"{t}_obs"].between(ok[f"{t}_lo"], ok[f"{t}_hi"])
        width = ok[f"{t}_hi"] - ok[f"{t}_lo"]
        for (model, lead), idx in ok.groupby(["model", "lead"]).groups.items():
            rows.append({"model": model, "target": t, "lead": lead, "n": len(idx),
                         "coverage": float(inside.loc[idx].mean()), "mean_width": float(width.loc[idx].mean())})
    return pd.DataFrame(rows)


def load(path=None) -> dict:
    path = path or INTERVALS_JSON
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> dict:
    from src import backtest
    from src.daily import load_daily
    from src.forecast import registry

    daily = load_daily()
    live = {m.name for m in registry.production_models()}

    def fresh():                                                       # unfitted: each backtest fits its own copy
        return [m for m in registry.all_models() if m.name in live]
    # Calibration errors from two out-of-sample stretches: 2008–2016 (models fitted ≤ 2007; includes the cycle-24
    # maximum) and validation 2017–2019 (fitted ≤ 2016; solar minimum). Validation alone is too quiet (D-23, D-45).
    first, last = pd.Timestamp(CAL_START), backtest.period("validation", daily)[1]
    val_first = backtest.period("validation", daily)[0]
    fc = pd.concat([backtest.run(fresh(), daily, first, val_first - pd.Timedelta(days=1)),
                    backtest.run(fresh(), daily, val_first, last)], ignore_index=True)
    table = calibrate(fc)
    INTERVALS_JSON.parent.mkdir(parents=True, exist_ok=True)
    INTERVALS_JSON.write_text(json.dumps(table, indent=1), encoding="utf-8")
    out = config.FORECAST_REPORTS_DIR / "metrics"
    fc.to_csv(config.FORECAST_REPORTS_DIR / "calibration_forecasts.csv.gz", index=False)  # reused for storm rules
    check_first, check_last = backtest.period("recent", daily)
    recent = apply(backtest.hindcast(daily, check_first, check_last), table)
    cov = coverage(recent)
    cov.to_csv(out / "recent_interval_coverage.csv", index=False)
    print(f"calibrated {sorted(table)} on {first.date()} -> {last.date()}")
    print(f"coverage on the recent hindcast ({check_first.date()} -> {check_last.date()}), target {LEVEL:.0%}:")
    print(cov.pivot_table(index=["target", "model"], columns="lead", values="coverage").round(2).to_string())
    return {"table": table, "coverage": cov}


if __name__ == "__main__":
    main()
