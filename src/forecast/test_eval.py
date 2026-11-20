"""One-time test evaluation (docs/plans/PLAN.md §7, DECISIONS D-08, D-51): 2020-01-01 → last definitive day.

Every model is fitted on data up to 2019-12-31 (the production window), exactly as it runs live, and scored once on
the test period, which no choice has looked at. The headline model was fixed BEFORE this run by the rule in
docs/plans/PLAN.md §6 (highest mean validation skill over lead days 1–7): HistGB for values, the storm classifier for warnings.

A marker file records the run. Running again refuses unless --force, so the test score cannot be repeated until it
looks good; a forced re-run must be justified in DECISIONS.md.

    python -m src.forecast.test_eval
"""
import argparse
import json

import pandas as pd

from src import backtest, config, scorecard
from src.forecast import arima, chronos_model, gbm, intervals, registry, storm

MARKER = config.FORECAST_REPORTS_DIR / "test_scored.json"
HEADLINE = {"value": "histgb", "storm": storm.NAME}


def rows_before_test(daily: pd.DataFrame) -> pd.DataFrame:
    """Train + validation: everything before the test years."""
    return backtest.training_rows(daily, pd.Timestamp(f"{config.TEST_START_YEAR}-01-01"))


def _all_models_fitted_to_2019(daily):
    """Every model with its selected settings, fitted on data up to 2019-12-31. Fitted afresh rather than loaded:
    since D-63 the live bundles also cover the test years. Fitting is deterministic, so these are the models that
    ran live before D-63."""
    params, log_ap = gbm.load_params()
    models = registry.baselines() + [gbm.HistGBDirect(params, log_ap=log_ap)]
    models += arima.default_models(arima.load_settings())
    if chronos_model.available():
        models.append(chronos_model.ChronosForecaster())
    fit_rows = rows_before_test(daily)
    return [m.fit(fit_rows) for m in models]


def main(force: bool = False) -> dict:
    from src.daily import load_daily

    if MARKER.exists() and not force:
        raise SystemExit(f"test already scored ({MARKER.name}); re-running needs --force and a DECISIONS entry")
    daily = load_daily()
    first, last = backtest.period("test", daily)
    origins = backtest.origins_for(first, last)

    parts = []
    for model in _all_models_fitted_to_2019(daily):
        parts.append(model.predict(daily, origins).assign(model=model.name))
        print(f"forecast {model.name}")
    fc = pd.concat(parts, ignore_index=True)
    fc = backtest.attach_actuals(fc[fc["target_date"].between(first, last)], daily)
    fc = fc[fc["obs_definitive"]].reset_index(drop=True)
    fc = intervals.apply(fc, intervals.load())
    fc = pd.concat([fc, backtest.noaa_rows(daily, first, last)], ignore_index=True)

    out = config.FORECAST_REPORTS_DIR / "metrics"
    leads, storms, cov = scorecard.lead_table(fc), scorecard.storm_table(fc), intervals.coverage(fc)
    leads.to_csv(out / "test_leads.csv", index=False)
    storms.to_csv(out / "test_storms.csv", index=False)
    cov.to_csv(out / "test_interval_coverage.csv", index=False)
    fc.to_csv(config.FORECAST_REPORTS_DIR / "test_forecasts.csv.gz", index=False)

    warn_model = storm.StormClassifier().fit(rows_before_test(daily))
    warn_model.thresholds_ = storm.StormClassifier.load().thresholds_     # chosen on 2008–2016
    w = storm.attach_obs(warn_model.predict(daily, origins), daily)
    w = w[w["target_date"].between(first, last) & w["obs_definitive"]]
    warn = storm.table(w)
    warn.to_csv(out / "test_storm_warning.csv", index=False)
    w.to_csv(config.FORECAST_REPORTS_DIR / "test_storm_warning_forecasts.csv.gz", index=False)

    MARKER.write_text(json.dumps({"scored_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
                                  "period": [str(first.date()), str(last.date())], "headline": HEADLINE,
                                  "models": sorted(fc["model"].unique())}, indent=2), encoding="utf-8")
    print(f"test {first.date()} -> {last.date()}: {fc['origin'].nunique():,} issue days, "
          f"{int(daily.loc[first:last, 'kpmax'].ge(config.STORM_THRESHOLD).sum())} storm days")
    return {"leads": leads, "storms": storms, "coverage": cov, "warning": warn}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-score although the test was already scored")
    main(force=ap.parse_args().force)
