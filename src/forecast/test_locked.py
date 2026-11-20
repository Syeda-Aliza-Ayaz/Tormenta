"""One-time test of the locked model (DECISIONS D-76). Runs once; a marker file blocks a second run.

Locked model: `sw_rec_poisson_imagery` (HistGB + solar wind + 27-day echo + coronal holes, Poisson loss, live
settings). Fitted on definitive days up to 2019-12-31, forecasting every issue day whose targets fall in
2020-01-01 → 2026-06-30. Compared on the same days with the live HistGB as tested in D-62
(`reports/forecast/test_forecasts.csv.gz`), NOAA (Ap, days 1–3) and the 27-day average.

    python -m src.forecast.test_locked              the test (once)
    python -m src.forecast.test_locked --rescore    score the saved forecasts again after a scoring fix (no refit)
"""
import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from src import config, scorecard
from src.daily import load_daily
from src.forecast import gbm, storm, validate_yearly as V

LOCKED = "sw_rec_poisson_imagery"
FIRST, LAST = pd.Timestamp("2020-01-01"), pd.Timestamp("2026-06-30")
OUT = config.FORECAST_REPORTS_DIR / "test_locked"
MARKER = OUT / "test_scored.json"
D62 = config.FORECAST_REPORTS_DIR / "test_forecasts.csv.gz"
D62_STORM = config.FORECAST_REPORTS_DIR / "test_storm_warning_forecasts.csv.gz"


def fit_and_forecast(daily: pd.DataFrame) -> tuple:
    """The D-68 harness block, with the fit ending on 2019-12-31 and the targets in the test period."""
    variant = V.VARIANTS[LOCKED]()
    variant.allow_test = True                     # test-period images are read here only
    params, _ = gbm.load_params()
    feats = {h: variant.features(daily, h) for h in config.FORECAST_LEADS}
    origins = pd.date_range(FIRST - pd.Timedelta(days=max(config.FORECAST_LEADS)), LAST - pd.Timedelta(days=1), freq="D")
    ref = daily[config.FORECAST_TARGETS].rolling(config.RECURRENCE_DAYS, min_periods=config.RECURRENCE_DAYS // 2).mean()
    vals, probs, t0 = [], [], time.time()
    for i, h in enumerate(config.FORECAST_LEADS, 1):
        X = feats[h]
        tgt = daily[config.FORECAST_TARGETS].shift(-h)
        tdate = X.index + pd.Timedelta(days=h)
        tdef = daily["definitive"].reindex(tdate).fillna(False).to_numpy()
        base = (X.index >= config.FORECAST_TRAIN_START) & (tdate < FIRST) & daily["definitive"].to_numpy() & tdef \
            & X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1).to_numpy()
        cols = [c for c in X.columns if X.loc[base, c].notna().any()]
        Xo = X.loc[origins, cols]
        out = pd.DataFrame({"origin": origins, "lead": h, "target_date": origins + pd.Timedelta(days=h)})
        for t in config.FORECAST_TARGETS:
            k = base & tgt[t].notna().to_numpy()
            m = gbm._model({**params[t], **variant.reg_extra}).fit(X.loc[k, cols], tgt.loc[k, t])
            out[t] = np.clip(m.predict(Xo), 0, 400 if t == "ap" else 9)
            out[f"{t}_ref"] = ref[t].reindex(origins).to_numpy()
        vals.append(out)
        k = base & tgt["kpmax"].notna().to_numpy()
        c = HistGradientBoostingClassifier(**variant.clf_params(), early_stopping=False, random_state=config.RANDOM_STATE) \
            .fit(X.loc[k, cols], (tgt.loc[k, "kpmax"] >= config.STORM_THRESHOLD).astype(int))
        probs.append(pd.DataFrame({"origin": origins, "lead": h, "target_date": origins + pd.Timedelta(days=h),
                                   "storm_prob": c.predict_proba(Xo)[:, 1]}))
        spent = time.time() - t0
        print(f"  [{i}/7] lead day {h} fitted | elapsed {spent / 60:.1f} min | about {spent / i * (7 - i) / 60:.0f} min left",
              flush=True)
    keep = lambda f: f[f["target_date"].between(FIRST, LAST)]  # noqa: E731
    vals, probs = keep(pd.concat(vals, ignore_index=True)), keep(pd.concat(probs, ignore_index=True))
    obs = daily.reindex(vals["target_date"])
    for t in config.FORECAST_TARGETS:
        vals[f"{t}_obs"] = obs[t].to_numpy()
    vals["obs_definitive"] = obs["definitive"].fillna(False).to_numpy()
    kp = daily["kpmax"].reindex(probs["target_date"])
    probs = probs.assign(kpmax_obs=kp.to_numpy(), storm_obs=(kp >= config.STORM_THRESHOLD).to_numpy(),
                         obs_definitive=daily["definitive"].reindex(probs["target_date"]).fillna(False).to_numpy())
    return vals, probs


def diebold_mariano(e1: np.ndarray, e2: np.ndarray, h: int) -> tuple:
    """DM statistic and two-sided p-value for squared errors, Newey–West variance with lag h-1 (D-76)."""
    from scipy.stats import norm
    d = e1 ** 2 - e2 ** 2
    n, mean = len(d), d.mean()
    gamma = [np.mean((d[k:] - mean) * (d[:n - k] - mean)) for k in range(h)]
    var = gamma[0] + 2 * sum((1 - k / h) * gamma[k] for k in range(1, h))
    stat = mean / np.sqrt(var / n)
    return float(stat), float(2 * (1 - norm.cdf(abs(stat))))


def skill(g: pd.DataFrame, col: str, target: str = "ap") -> float:
    per_lead = g.groupby("lead").apply(lambda x: 1 - ((x[col] - x[f"{target}_obs"]) ** 2).sum()
                                       / ((x[f"{target}_ref"] - x[f"{target}_obs"]) ** 2).sum())
    return float(per_lead.mean())


def score(vals: pd.DataFrame, probs: pd.DataFrame) -> dict:
    d62 = pd.read_csv(D62, parse_dates=["origin", "target_date"])
    hist = d62[d62["model"] == "histgb"][["origin", "lead", "ap", "kpmax"]].rename(columns={"ap": "ap_hist", "kpmax": "kpmax_hist"})
    noaa = d62[d62["model"] == "noaa"][["origin", "lead", "ap"]].rename(columns={"ap": "ap_noaa"})
    v = vals[vals["obs_definitive"]].merge(hist, on=["origin", "lead"])
    rmse = lambda a, b: float(np.sqrt(np.mean((a - b) ** 2)))  # noqa: E731
    rows = []
    for h, g in v.groupby("lead"):
        # NOAA is compared only on the days it issued a forecast (one day-1 forecast is missing)
        n = g.merge(noaa, on=["origin", "lead"]).dropna(subset=["ap_noaa"]) if h <= 3 else None
        rows.append({"lead": int(h), "days": len(g),
                     "ap_rmse_locked": rmse(g["ap"], g["ap_obs"]), "ap_rmse_histgb": rmse(g["ap_hist"], g["ap_obs"]),
                     "ap_rmse_noaa": rmse(n["ap_noaa"], n["ap_obs"]) if n is not None else np.nan,
                     "ap_rmse_locked_noaa_days": rmse(n["ap"], n["ap_obs"]) if n is not None else np.nan,
                     "noaa_days": len(n) if n is not None else 0,
                     "ap_rmse_trailing27": rmse(g["ap_ref"], g["ap_obs"]),
                     "kpmax_rmse_locked": rmse(g["kpmax"], g["kpmax_obs"]), "kpmax_rmse_histgb": rmse(g["kpmax_hist"], g["kpmax_obs"]),
                     "dm_vs_histgb": diebold_mariano((g["ap"] - g["ap_obs"]).to_numpy(), (g["ap_hist"] - g["ap_obs"]).to_numpy(), int(h)),
                     "dm_vs_noaa": diebold_mariano((n["ap"] - n["ap_obs"]).to_numpy(), (n["ap_noaa"] - n["ap_obs"]).to_numpy(), int(h))
                     if n is not None else (np.nan, np.nan)})
    leads = pd.DataFrame(rows)
    sk_locked, sk_hist = skill(v, "ap"), skill(v, "ap_hist")
    # 30-day block bootstrap of the skill difference (locked − live HistGB), days 1–7
    rng = np.random.default_rng(config.RANDOM_STATE)
    v["block"] = (v["target_date"] - FIRST).dt.days // 30
    blocks = v["block"].unique()
    diffs = []
    for _ in range(1000):
        pick = rng.choice(blocks, len(blocks))
        b = pd.concat([v[v["block"] == k] for k in pick])
        diffs.append(skill(b, "ap") - skill(b, "ap_hist"))
    # storm warnings: thresholds from the locked model's out-of-sample 2011–2019 harness probabilities
    harness = pd.read_csv(V.OUT / LOCKED / "storm_probs.csv", parse_dates=["target_date"])
    th = storm.tune_thresholds(harness)
    p = probs[probs["obs_definitive"]]
    live = pd.read_csv(D62_STORM, parse_dates=["origin", "target_date"])
    live = live[live["obs_definitive"]]
    storms = []
    for h in config.FORECAST_LEADS:
        a, b = p[p["lead"] == h], live[live["lead"] == h]
        ca = scorecard.contingency(a["storm_prob"] >= th[h], a["storm_obs"])
        cb = scorecard.contingency(b["warning"].astype(bool), b["storm_obs"])
        storms.append({"lead": h, "threshold": th[h], "storm_days": int(a["storm_obs"].sum()),
                       "hss_locked": ca["hss"], "pod_locked": ca["pod"], "far_locked": ca["far"],
                       "hss_histgb": cb["hss"], "pod_histgb": cb["pod"], "far_histgb": cb["far"]})
    storms = pd.DataFrame(storms)
    d1 = leads.set_index("lead").loc[1]
    hss13 = storms[storms["lead"] <= 3]
    rule = {
        "a pooled Ap skill better than live HistGB": sk_locked > sk_hist,
        "a day-1 Ap RMSE better than live HistGB": d1["ap_rmse_locked"] < d1["ap_rmse_histgb"],
        "b storm Heidke days 1-3 not lower by more than 0.01": hss13["hss_locked"].mean() - hss13["hss_histgb"].mean() >= -0.01,
    }
    return {"leads": leads, "storms": storms, "skill_locked": sk_locked, "skill_histgb": sk_hist,
            "skill_diff_ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
            "rule": rule}


def write_scores(vals: pd.DataFrame, probs: pd.DataFrame, extra: dict = None) -> dict:
    print("  scoring (with a 1000-sample block bootstrap)", flush=True)
    res = score(vals, probs)
    res["leads"].to_csv(OUT / "leads.csv", index=False)
    res["storms"].to_csv(OUT / "storms.csv", index=False)
    summary = {"model": LOCKED, "scored_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
               "skill_locked": res["skill_locked"], "skill_histgb": res["skill_histgb"],
               "skill_diff_ci95": res["skill_diff_ci95"], "rule": {k: bool(v) for k, v in res["rule"].items()},
               **(extra or {})}
    MARKER.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return res | {"summary": summary}


def rescore():
    """Score the saved test forecasts again after a scoring fix (D-77). Nothing is refitted or re-forecast."""
    if not MARKER.exists():
        raise SystemExit("no scored test to re-score")
    first = json.loads(MARKER.read_text(encoding="utf-8"))
    vals = pd.read_csv(OUT / "forecasts.csv.gz", parse_dates=["origin", "target_date"])
    probs = pd.read_csv(OUT / "storm_probs.csv.gz", parse_dates=["origin", "target_date"])
    return write_scores(vals, probs, {"first_scored_at": first.get("first_scored_at", first["scored_at"]),
                                      "rescored": "NOAA gap excluded from the day-1 comparison (D-77)"})


def main():
    import sys
    if "--rescore" in sys.argv:
        res = rescore()
    else:
        if MARKER.exists():
            raise SystemExit("the locked model's test is already scored; a second run is not allowed (D-76)")
        OUT.mkdir(parents=True, exist_ok=True)
        daily = load_daily()
        print(f"locked test: {LOCKED}, fit <= 2019-12-31, targets {FIRST.date()} -> {LAST.date()}", flush=True)
        vals, probs = fit_and_forecast(daily)
        vals.to_csv(OUT / "forecasts.csv.gz", index=False)
        probs.to_csv(OUT / "storm_probs.csv.gz", index=False)
        res = write_scores(vals, probs)
    summary = res["summary"]
    pd.set_option("display.width", 250)
    print(res["leads"].round(3).to_string(index=False))
    print(res["storms"].round(3).to_string(index=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
