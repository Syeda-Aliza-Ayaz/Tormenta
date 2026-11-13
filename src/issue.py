"""Daily job (PLAN.md §8): issue today's 7-day forecasts, save NOAA's, score everything whose day has arrived.

Run by .github/workflows/daily.yml at 02:00 UTC, or by hand:
    python -m src.issue               # download GFZ + NOAA, update forecasts/
    python -m src.issue --no-download # use data/raw as it is (NOAA is skipped)

Files written (all in forecasts/, all committed):
  log.csv        APPEND-ONLY. One row per model × lead day for every issue. Existing rows are never changed;
                 rerunning on the same day adds nothing. Past origins are never backfilled (DECISIONS D-07).
  scores.csv     rebuilt from log.csv + GFZ every run: each forecast whose target day GFZ has published, with the
                 observed value and its quality flag (it changes when provisional values become definitive).
  recent.csv     the last 60 days of observed Ap / max Kp, so the apps can draw history without calling GFZ.
  noaa_live.csv  NOAA's 27-day outlook and 3-day forecast, parsed; the raw texts go to forecasts/noaa/.
"""
import argparse

import pandas as pd

from src import backtest, config
from src.daily import build_daily, check
from src.forecast import intervals, registry, storm
from src.ingest import fetch_noaa
from src.ingest.fetch_gfz import download_gfz, load_gfz_daily

LOG_COLUMNS = ["issued_at", "origin", "origin_flag", "model", "model_version", "lead", "target_date",
               "ap", "ap_lo", "ap_hi", "kpmax", "kpmax_lo", "kpmax_hi"]
KEY = ["origin", "model", "lead"]


def choose_origin(daily: pd.DataFrame, today: pd.Timestamp):
    """The last complete day GFZ has published, if it is recent enough to forecast from; else None."""
    complete = daily.dropna(subset=config.FORECAST_TARGETS)
    origin = complete.index[complete.index < today].max()
    if pd.isna(origin) or (today - origin).days > config.MAX_ORIGIN_AGE_DAYS:
        return None
    return origin


def production_window(daily: pd.DataFrame) -> pd.DataFrame:
    """Fixed fitting window for the live models: train + validation (everything before the test years)."""
    return backtest.training_rows(daily, pd.Timestamp(f"{config.TEST_START_YEAR}-01-01"))


def issue(daily: pd.DataFrame, origin: pd.Timestamp, models, issued_at: pd.Timestamp) -> pd.DataFrame:
    fit_rows = production_window(daily)
    parts = []
    for model in models:
        fc = model.fit(fit_rows).predict(daily, [origin])
        parts.append(fc.assign(model=model.name, model_version=model.version))
    new = intervals.apply(pd.concat(parts, ignore_index=True), intervals.load())   # 80% ranges (D-45)
    new["issued_at"] = issued_at
    new["origin_flag"] = int(daily.loc[origin, "gfz_flag"])
    return new.reindex(columns=LOG_COLUMNS)


def load_log(path=None) -> pd.DataFrame:
    path = path or config.FORECAST_LOG             # resolved at call time (tests point config elsewhere)
    if not path.exists():
        return pd.DataFrame(columns=LOG_COLUMNS)
    return pd.read_csv(path, parse_dates=["issued_at", "origin", "target_date"])


def append(log: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Existing rows untouched; only (origin, model, lead) combinations not yet in the log are added."""
    if len(log):
        seen = pd.MultiIndex.from_frame(log[KEY])
        new = new[~pd.MultiIndex.from_frame(new[KEY]).isin(seen)]
    return pd.concat([log, new], ignore_index=True) if len(log) else new.reset_index(drop=True)


SCORE_COLUMNS = LOG_COLUMNS + [f"{t}_obs" for t in config.FORECAST_TARGETS] + [
    "obs_definitive", "obs_flag"] + [f"{t}_err" for t in config.FORECAST_TARGETS]
NOAA_COLUMNS = ["product", "issued", "origin", "lead", "target_date", "f107", "ap", "kpmax"]


def score(log: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    if not len(log):
        return pd.DataFrame(columns=SCORE_COLUMNS)
    scored = backtest.attach_actuals(log, daily)
    scored["obs_flag"] = daily["gfz_flag"].reindex(scored["target_date"]).to_numpy()
    scored = scored.dropna(subset=[f"{t}_obs" for t in config.FORECAST_TARGETS], how="all")
    for t in config.FORECAST_TARGETS:
        scored[f"{t}_err"] = scored[t] - scored[f"{t}_obs"]
    return scored.reset_index(drop=True)[SCORE_COLUMNS]


def recent(daily: pd.DataFrame) -> pd.DataFrame:
    cols = config.FORECAST_TARGETS + ["f107_obs", "gfz_flag"]
    return daily.loc[config.RECENT_START:, cols].dropna(subset=config.FORECAST_TARGETS)


NOAA_PRODUCTS = {"27do": (config.NOAA_27DO, fetch_noaa.parse_27do),
                 "3day": (config.NOAA_3DAY, fetch_noaa.parse_3day)}


def save_noaa(fetch=fetch_noaa.fetch_text) -> pd.DataFrame:
    """Fetch, keep the raw text, parse, and merge into noaa_live.csv. A failed product is a warning, not an error."""
    frames = []
    for product, (url, parse) in NOAA_PRODUCTS.items():
        try:
            text = fetch(url)
            parsed = parse(text).assign(product=product)
        except Exception as exc:                      # noqa: BLE001 - NOAA is a benchmark; never block the forecast
            print(f"WARNING: NOAA {product} not saved ({type(exc).__name__}: {exc})")
            continue
        raw = config.NOAA_LIVE_DIR / product / f"{parsed['issued'].iloc[0]:%Y%m%d_%H%M}.txt"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(text, encoding="utf-8")
        frames.append(parsed)
    out = pd.concat([load_noaa_live(), *frames], ignore_index=True).reindex(columns=NOAA_COLUMNS)
    out = out.drop_duplicates(subset=["product", "issued", "target_date"], keep="first")
    return out.sort_values(["product", "issued", "target_date"], ignore_index=True)


def load_noaa_live(path=None) -> pd.DataFrame:
    path = path or config.NOAA_LIVE_CSV
    if not path.exists():
        return pd.DataFrame(columns=NOAA_COLUMNS)
    return pd.read_csv(path, parse_dates=["issued", "origin", "target_date"])


def run(download: bool = True, now: pd.Timestamp = None, models=None) -> dict:
    now = now or pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")
    if download:
        download_gfz()
    daily = build_daily(load_gfz_daily())
    check(daily)

    log = load_log()
    origin = choose_origin(daily, now.normalize())
    if origin is None:
        print(f"WARNING: GFZ has not published yesterday yet (last complete day "
              f"{daily.dropna(subset=config.FORECAST_TARGETS).index.max().date()}); no forecast issued.")
        n_new = 0
    else:
        new = issue(daily, origin, models or registry.production_models(), now)
        before = len(log)
        log = append(log, new)
        n_new = len(log) - before
        print(f"origin {origin.date()} (GFZ flag {int(daily.loc[origin, 'gfz_flag'])}): "
              f"{n_new} new forecast rows ({'already issued today' if not n_new else 'issued'})")
    storm_log = load_storm_log()
    if origin is not None:
        new_storm = issue_storm(daily, origin, now)
        if new_storm is not None:
            storm_log = append_storm(storm_log, new_storm)

    config.FORECASTS_DIR.mkdir(parents=True, exist_ok=True)
    log.to_csv(config.FORECAST_LOG, index=False)
    scores = score(log, daily)
    scores.to_csv(config.FORECAST_SCORES, index=False)
    recent(daily).to_csv(config.FORECAST_RECENT)
    noaa = save_noaa() if download else load_noaa_live()
    noaa.to_csv(config.NOAA_LIVE_CSV, index=False)
    storm_log.reindex(columns=STORM_COLUMNS).to_csv(config.STORM_LOG, index=False)
    score_storm(storm_log, daily).to_csv(config.STORM_SCORES, index=False)
    print(f"log {len(log)} rows | scored {len(scores)} | NOAA rows {len(noaa)} | storm log {len(storm_log)} rows")
    return {"origin": origin, "new_rows": n_new, "log": log, "scores": scores}


STORM_COLUMNS = ["issued_at", "origin", "model_version", "lead", "target_date", "storm_prob", "threshold", "warning"]
STORM_KEY = ["origin", "lead"]


def issue_storm(daily: pd.DataFrame, origin: pd.Timestamp, issued_at: pd.Timestamp):
    """Storm risk for D+1 … D+7 from the saved storm classifier, or None if there is no bundle."""
    if not storm.BUNDLE.exists():
        return None
    model = storm.StormClassifier.load()
    fc = model.predict(daily, [origin]).assign(issued_at=issued_at, model_version=f"until {model.trained_until_}")
    return fc.reindex(columns=STORM_COLUMNS)


def load_storm_log(path=None) -> pd.DataFrame:
    path = path or config.STORM_LOG
    if not path.exists():
        return pd.DataFrame(columns=STORM_COLUMNS)
    return pd.read_csv(path, parse_dates=["issued_at", "origin", "target_date"])


def append_storm(log: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Same rule as the forecast log: existing rows untouched, a key already issued is never issued again."""
    if len(log):
        new = new[~pd.MultiIndex.from_frame(new[STORM_KEY]).isin(pd.MultiIndex.from_frame(log[STORM_KEY]))]
    return pd.concat([log, new], ignore_index=True) if len(log) else new.reset_index(drop=True)


def score_storm(log: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    cols = STORM_COLUMNS + ["kpmax_obs", "obs_definitive", "storm_obs"]
    if not len(log):
        return pd.DataFrame(columns=cols)
    return storm.attach_obs(log, daily).reset_index(drop=True)[cols]


def _github_output(result: dict) -> None:
    import os
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            origin = result["origin"].date() if result["origin"] is not None else "none"
            fh.write(f"origin={origin}\nnew_rows={result['new_rows']}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true", help="use data/raw as it is; skip NOAA")
    _github_output(run(download=not ap.parse_args().no_download))
