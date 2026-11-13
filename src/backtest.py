"""Rolling-origin backtest (PLAN.md §7): one forecast per day, each built only from data up to its issue day.

    python -m src.backtest                 # validation period (2017–2019), every registered model
    python -m src.backtest --period recent # hindcast: the LIVE models on the days after the last definitive day

The test period (2020 → last definitive day) is scored once per model version, by the fixed selection rule on
day 6 — not from this command (DECISIONS D-08).

"recent" (DECISIONS D-43) covers the days GFZ has published since its last definitive day (provisional / nowcast
values): in neither validation nor test, and after every live model's training data (≤ 2019). It runs the
production models exactly as the daily job does, issued in hindsight but from data up to each origin only. It gives
statistics now; the live log stays the proof that forecasts were written before their days.
"""
import argparse

import pandas as pd

from src import config, scorecard
from src.daily import last_definitive, load_daily
from src.forecast import registry
from src.ingest.fetch_noaa import load_rsga


def period(name: str, daily: pd.DataFrame) -> tuple:
    """(first, last) target day of a period. Each period is fitted on everything before it."""
    if name == "validation":
        return pd.Timestamp(f"{config.VAL_YEARS[0]}-01-01"), pd.Timestamp(f"{config.VAL_YEARS[1]}-12-31")
    if name == "test":
        return pd.Timestamp(f"{config.TEST_START_YEAR}-01-01"), last_definitive(daily)
    if name == "recent":
        return last_definitive(daily) + pd.Timedelta(days=1), daily.dropna(subset=config.FORECAST_TARGETS).index.max()
    raise ValueError(name)


def training_rows(daily: pd.DataFrame, before: pd.Timestamp) -> pd.DataFrame:
    """Definitive days from FORECAST_TRAIN_START up to the day before `before`."""
    rows = daily.loc[config.FORECAST_TRAIN_START: before - pd.Timedelta(days=1)]
    return rows[rows["definitive"]]


def origins_for(first: pd.Timestamp, last: pd.Timestamp) -> pd.DatetimeIndex:
    """Issue days whose D+1 … D+7 touch [first, last]; rows outside are dropped after forecasting,
    so every target day in the period gets all seven lead days."""
    lead_max = max(config.FORECAST_LEADS)
    return pd.date_range(first - pd.Timedelta(days=lead_max), last - pd.Timedelta(days=1), freq="D")


def attach_actuals(fc: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    obs = daily.reindex(fc["target_date"])
    return fc.assign(**{f"{t}_obs": obs[t].to_numpy() for t in config.FORECAST_TARGETS},
                     obs_definitive=obs["definitive"].fillna(False).to_numpy())


def run(models, daily: pd.DataFrame, first: pd.Timestamp, last: pd.Timestamp) -> pd.DataFrame:
    train = training_rows(daily, first)
    origins = origins_for(first, last)
    parts = []
    for model in models:
        model.fit(train)
        fc = model.predict(daily, origins)
        parts.append(fc.assign(model=model.name))
    fc = pd.concat(parts, ignore_index=True)
    fc = fc[fc["target_date"].between(first, last)]
    fc = attach_actuals(fc, daily)
    return fc[fc["obs_definitive"]].reset_index(drop=True)


def hindcast(daily: pd.DataFrame, first: pd.Timestamp, last: pd.Timestamp) -> pd.DataFrame:
    """The production models (what the daily job issues), forecasting every origin as if live; scored against
    whatever GFZ has published (provisional values included, flagged in obs_definitive)."""
    from src.issue import production_window
    fit_rows = production_window(daily)
    origins = origins_for(first, last)
    parts = []
    for model in registry.production_models():
        parts.append(model.fit(fit_rows).predict(daily, origins).assign(model=model.name))
    fc = pd.concat(parts, ignore_index=True)
    fc = attach_actuals(fc[fc["target_date"].between(first, last)], daily)
    return fc.dropna(subset=[f"{t}_obs" for t in config.FORECAST_TARGETS], how="all").reset_index(drop=True)


def noaa_rows(daily: pd.DataFrame, first: pd.Timestamp, last: pd.Timestamp,
              definitive_only: bool = True) -> pd.DataFrame:
    """NOAA's archived day 1–3 Ap forecast (RSGA) as model 'noaa', scored like ours. No max Kp in RSGA."""
    if not config.NOAA_RSGA_CSV.exists():
        return pd.DataFrame()
    rsga = load_rsga()
    rsga = rsga[rsga["lead"].isin(config.FORECAST_LEADS) & rsga["target_date"].between(first, last)]
    # one report per origin: if NOAA reissued, keep the latest
    rsga = rsga.sort_values("issued").drop_duplicates(subset=["origin", "lead"], keep="last")
    fc = rsga[["origin", "lead", "target_date", "ap"]].assign(kpmax=float("nan"), model="noaa")
    fc = attach_actuals(fc, daily)
    keep = fc["obs_definitive"] if definitive_only else fc["ap_obs"].notna()
    return fc[keep].reset_index(drop=True)


def main(name: str = "validation") -> dict:
    daily = load_daily()
    first, last = period(name, daily)
    if name == "recent":
        fc = pd.concat([hindcast(daily, first, last), noaa_rows(daily, first, last, definitive_only=False)],
                       ignore_index=True)
    else:
        fc = run(registry.all_models(), daily, first, last)
        fc = pd.concat([fc, noaa_rows(daily, first, last)], ignore_index=True)
    leads, storms = scorecard.lead_table(fc), scorecard.storm_table(fc)
    out = config.FORECAST_REPORTS_DIR / "metrics"
    out.mkdir(parents=True, exist_ok=True)
    leads.to_csv(out / f"{name}_leads.csv", index=False)
    storms.to_csv(out / f"{name}_storms.csv", index=False)
    print(f"{name}: target days {first.date()} -> {last.date()}, {fc['origin'].nunique():,} issue days")
    return {"forecasts": fc, "leads": leads, "storms": storms}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="validation", choices=["validation", "recent"])
    main(ap.parse_args().period)
