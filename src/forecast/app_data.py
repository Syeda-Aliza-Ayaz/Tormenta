"""Files the app's "Try it yourself" panel reads (no model training, no network):

  forecasts/past_forecasts.csv.gz   out-of-sample forecasts for every issue day from 2020-01-01: the one-time test
                                    run (models fitted ≤ 2019, D-52) followed by the recent hindcast (D-43). The
                                    storm classifier's chances are stored as model "storm_warning".
  forecasts/recent.csv              observed Ap / max Kp / F10.7 since RECENT_START (also refreshed by the daily job)

    python -m src.forecast.app_data
"""
import pandas as pd

from src import backtest, config
from src.daily import load_daily
from src.forecast import intervals, storm

MODELS = ["histgb", "arimax", "noaa", "trailing27", "persistence", "recurrence27"]
COLUMNS = ["origin", "lead", "target_date", "model", "ap", "ap_lo", "ap_hi", "kpmax", "kpmax_lo", "kpmax_hi",
           "storm_prob", "warning"]


def past_forecasts(daily: pd.DataFrame) -> pd.DataFrame:
    rep = config.FORECAST_REPORTS_DIR
    test = pd.read_csv(rep / "test_forecasts.csv.gz", parse_dates=["origin", "target_date"])
    recent = pd.read_csv(rep / "recent_forecasts.csv.gz", parse_dates=["origin", "target_date"])
    recent = intervals.apply(recent, intervals.load())
    values = pd.concat([test, recent], ignore_index=True)
    values = values[values["model"].isin(MODELS)]

    warn_test = pd.read_csv(rep / "test_storm_warning_forecasts.csv.gz", parse_dates=["origin", "target_date"])
    first, last = backtest.period("recent", daily)
    warn_recent = storm.StormClassifier.load().predict(daily, backtest.origins_for(first, last))
    warn = pd.concat([warn_test, warn_recent], ignore_index=True).assign(model=storm.NAME)

    out = pd.concat([values, warn], ignore_index=True).reindex(columns=COLUMNS)
    out = out[out["target_date"] <= last].drop_duplicates(subset=["origin", "lead", "model"], keep="last")
    num = ["ap", "ap_lo", "ap_hi", "kpmax", "kpmax_lo", "kpmax_hi", "storm_prob"]
    out[num] = out[num].round(3)
    return out.sort_values(["origin", "model", "lead"], ignore_index=True)


def main():
    from src.issue import recent
    daily = load_daily()
    past = past_forecasts(daily)
    config.FORECASTS_DIR.mkdir(parents=True, exist_ok=True)
    past.to_csv(config.PAST_FORECASTS, index=False)
    recent(daily).to_csv(config.FORECAST_RECENT)
    print(f"past forecasts {past['origin'].min().date()} -> {past['origin'].max().date()}: {len(past):,} rows, "
          f"{config.PAST_FORECASTS.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
