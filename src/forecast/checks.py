"""Two measurements of known training/live differences (DECISIONS D-60, D-61). Neither changes a model.

  skew         Live forecasts read GFZ's newest values while they are still preliminary (nowcast, then provisional);
               the models were trained on definitive values (PLAN.md §3). The daily job commits the observations it
               used (forecasts/recent.csv), so git history holds each day's inputs as first published. For each
               live issue day, the production models forecast twice: from those inputs, and from the same days as
               GFZ publishes them now. The differences are reported per model and lead day, beside the size of the
               input revisions. Until GFZ marks those days definitive this measures the early revisions only.
  reliability  The storm classifier learned on years with 22% storm days; recent years have fewer storms. Its
               probabilities are grouped into bins and compared with how often a storm happened, on periods it
               never trained on: 2008–2016 (fitted ≤ 2007), validation 2017–2019 (fitted ≤ 2016) and the recent
               hindcast (production model). The test period is not used.

    python -m src.forecast.checks skew
    python -m src.forecast.checks reliability
"""
import argparse
import io
import subprocess

import numpy as np
import pandas as pd

from src import backtest, config
from src.daily import load_daily
from src.forecast import registry, storm

OUT = config.FORECAST_REPORTS_DIR / "metrics"
PROB_BINS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.6, 1.0]


# ── skew: preliminary inputs vs the same days as published now ─────────────────
def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True, check=True).stdout


def input_snapshots() -> dict:
    """{origin: observations as committed by the daily job for that origin} from the history of recent.csv."""
    path = config.FORECAST_RECENT.relative_to(config.ROOT).as_posix()
    snaps = {}
    for line in _git("log", "--all", "--format=%H %s", "--", path).splitlines():
        sha, subject = line.split(" ", 1)
        if not subject.startswith("Daily forecast: origin "):
            continue
        origin = pd.Timestamp(subject.split("origin ")[1].split(",")[0])
        if origin in snaps:
            continue
        snap = pd.read_csv(io.StringIO(_git("show", f"{sha}:{path}")), index_col="date", parse_dates=["date"])
        snaps[origin] = snap
    return dict(sorted(snaps.items()))


def _with_inputs(daily: pd.DataFrame, snap: pd.DataFrame, origin: pd.Timestamp) -> pd.DataFrame:
    """The daily table up to `origin`, with the snapshot's values on the days it covers."""
    d = daily.loc[:origin].copy()
    rows = snap.loc[snap.index.intersection(d.index)]
    for col in ("ap", "kpmax", "f107_obs"):          # the earliest snapshots have no F10.7 column
        if col in rows:
            d.loc[rows.index, col] = rows[col]
    return d


def skew(daily: pd.DataFrame) -> tuple:
    from src.issue import production_window
    snaps = input_snapshots()
    fit_rows = production_window(daily)
    models = [m.fit(fit_rows) for m in registry.production_models()]
    classifier = storm.StormClassifier.load()
    revisions, diffs = [], []
    for origin, snap in snaps.items():
        if origin not in daily.index:
            continue
        window = slice(origin - pd.Timedelta(days=config.FORECAST_HISTORY_DAYS), origin)
        early, now = _with_inputs(daily, snap, origin), daily.loc[:origin]
        for col in ("ap", "kpmax"):
            delta = (now.loc[window, col] - early.loc[window, col]).dropna()
            revisions.append({"origin": origin, "input": col, "days_revised": int((delta != 0).sum()),
                              "mean_abs_revision": float(delta.abs().mean()), "max_abs_revision": float(delta.abs().max())})
        for m in models:
            a = m.predict(early, [origin]).set_index("lead")
            b = m.predict(now, [origin]).set_index("lead")
            for t in config.FORECAST_TARGETS:
                diffs += [{"origin": origin, "model": m.name, "target": t, "lead": h,
                           "change": float(b.loc[h, t] - a.loc[h, t])} for h in config.FORECAST_LEADS]
        a = classifier.predict(early, [origin]).set_index("lead")["storm_prob"]
        b = classifier.predict(now, [origin]).set_index("lead")["storm_prob"]
        diffs += [{"origin": origin, "model": storm.NAME, "target": "storm_prob", "lead": h,
                   "change": float(b[h] - a[h])} for h in config.FORECAST_LEADS]
    revisions, diffs = pd.DataFrame(revisions), pd.DataFrame(diffs)
    summary = (diffs.assign(abs_change=diffs["change"].abs())
               .groupby(["model", "target", "lead"])
               .agg(issue_days=("origin", "nunique"), mean_abs_change=("abs_change", "mean"),
                    max_abs_change=("abs_change", "max"), mean_change=("change", "mean"))
               .reset_index())
    return revisions, summary


# ── reliability: storm probability vs observed storm frequency ─────────────────
def _probs(model: storm.StormClassifier, daily: pd.DataFrame, first, last, definitive: bool) -> pd.DataFrame:
    fc = storm.attach_obs(model.predict(daily, backtest.origins_for(first, last)), daily)
    keep = fc["target_date"].between(first, last) & (fc["obs_definitive"] if definitive else True)
    return fc[keep]


def reliability(daily: pd.DataFrame) -> tuple:
    t0, t1 = pd.Timestamp(storm.TUNE_START), pd.Timestamp(storm.TUNE_END)
    v0, v1 = backtest.period("validation", daily)
    r0, r1 = backtest.period("recent", daily)
    periods = {
        "2008-2016 (fit <= 2007)": _probs(storm.StormClassifier().fit(backtest.training_rows(daily, t0)),
                                          daily, t0, t1, True),
        "validation 2017-2019 (fit <= 2016)": _probs(storm.StormClassifier().fit(backtest.training_rows(daily, v0)),
                                                     daily, v0, v1, True),
        "recent (production model)": _probs(storm.StormClassifier.load(), daily, r0, r1, False),
    }
    bins, overall = [], []
    for name, fc in periods.items():
        fc = fc.assign(bin=pd.cut(fc["storm_prob"], PROB_BINS, include_lowest=True, right=False))
        g = fc.groupby("bin", observed=True).agg(n=("storm_prob", "size"), mean_prob=("storm_prob", "mean"),
                                                  storm_freq=("storm_obs", "mean"))
        bins.append(g.reset_index().assign(period=name, bin=lambda x: x["bin"].astype(str)))
        quiet = fc[~fc["storm_obs"]]
        overall.append({"period": name, "forecasts": len(fc), "mean_prob": fc["storm_prob"].mean(),
                        "storm_freq": fc["storm_obs"].mean(), "mean_prob_quiet_days": quiet["storm_prob"].mean(),
                        "brier": float(np.mean((fc["storm_prob"] - fc["storm_obs"]) ** 2))})
    cols = ["period", "bin", "n", "mean_prob", "storm_freq"]
    return pd.concat(bins, ignore_index=True)[cols], pd.DataFrame(overall)


def main(what: str):
    daily = load_daily()
    OUT.mkdir(parents=True, exist_ok=True)
    if what == "skew":
        revisions, summary = skew(daily)
        revisions.to_csv(OUT / "input_skew_revisions.csv", index=False)
        summary.to_csv(OUT / "input_skew_forecast_change.csv", index=False)
        print(revisions.round(2).to_string(index=False))
        print(summary.round(3).to_string(index=False))
    else:
        bins, overall = reliability(daily)
        bins.to_csv(OUT / "storm_reliability.csv", index=False)
        overall.to_csv(OUT / "storm_reliability_overall.csv", index=False)
        print(bins.round(3).to_string(index=False))
        print(overall.round(3).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["skew", "reliability"])
    main(ap.parse_args().what)
