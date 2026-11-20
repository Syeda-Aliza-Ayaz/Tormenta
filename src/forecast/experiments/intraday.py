"""Re-issue today and tomorrow every 3 hours (DECISIONS D-72). Experiment only: nothing live uses this module.

At update k (k = 1 … 7: 03, 06, … 21 UTC, k blocks of today ended) the models see
  - the live daily features as of yesterday (src/forecast/features.py, issue day D-1), and
  - today's ended Kp blocks and today's solar wind up to the update time.
Targets: today (lead 0) and tomorrow (lead 1): Ap, max Kp, storm day (max Kp >= 4.5).

    python -m src.forecast.experiments.intraday            # yearly validation 2011–2019 and the D-72 rule
"""
import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from src import config, scorecard
from src.daily import load_daily
from src.forecast import features as F, gbm, storm
from src.ingest.fetch_gfz import load_gfz_daily

UPDATES = range(1, 8)                       # k blocks ended: 03, 06, … 21 UTC
NAMES = {k: f"{3 * k:02d} UTC" for k in UPDATES}
YEARS = list(range(2011, 2020))
THRESHOLD_YEARS, SCORE_YEARS = (2011, 2014), (2015, 2019)
OUT = config.FORECAST_REPORTS_DIR / "experiments" / "intraday"
MIDNIGHT = config.FORECAST_REPORTS_DIR / "experiments" / "yearly" / "baseline"
KP_COLS = [f"kp{i}" for i in range(1, 9)]
# GFZ Kp (in thirds) → 3-hour ap
AP_OF_KP = np.array([0, 2, 3, 4, 5, 6, 7, 9, 12, 15, 18, 22, 27, 32, 39, 48, 56, 67, 80, 94, 111, 132, 154, 179, 207,
                     236, 300, 400], dtype=float)


def kp_to_ap(kp: np.ndarray) -> np.ndarray:
    idx = np.rint(np.asarray(kp, dtype=float) * 3)
    out = np.full(idx.shape, np.nan)
    ok = ~np.isnan(idx)
    out[ok] = AP_OF_KP[np.clip(idx[ok].astype(int), 0, 27)]
    return out


def block_features(blocks: pd.DataFrame, k: int) -> pd.DataFrame:
    """Today's ended blocks at update k. `blocks` holds kp1 … kp8 per UTC day; only the first k are read."""
    kp = blocks[KP_COLS[:k]].to_numpy(dtype=float)
    ap = kp_to_ap(kp)
    out = pd.DataFrame(index=blocks.index)
    out["blocks_known"] = k
    out["kp_sofar_max"] = np.nanmax(kp, axis=1) if k else np.nan
    out["ap_sofar_mean"] = np.nanmean(ap, axis=1)
    out["kp_last"] = kp[:, -1]
    out["kp_last_change"] = kp[:, -1] - kp[:, -2] if k >= 2 else np.nan
    out["storm_blocks_sofar"] = (kp >= config.STORM_THRESHOLD).sum(axis=1)
    out.loc[np.isnan(kp).any(axis=1), ["kp_sofar_max", "ap_sofar_mean", "kp_last", "kp_last_change"]] = np.nan
    return out


def solar_wind_hourly() -> pd.DataFrame:
    h = pd.read_csv(config.PROCESSED_CSV, usecols=["time", "speed", "bz_gsm"], parse_dates=["time"]).set_index("time")
    h["vbs"] = h["speed"] * (-h["bz_gsm"]).clip(lower=0) / 1000
    return h


def solar_wind_features(hourly: pd.DataFrame, k: int) -> pd.DataFrame:
    """Today's solar wind from 00 UTC up to the update time (3k hours), and its last 3 hours. Hourly values are
    stamped at the start of their hour, so the hour starting at 3k-1 ends exactly at the update time."""
    hours = hourly.index.hour
    sofar = hourly[hours < 3 * k]
    last3 = hourly[(hours >= 3 * k - 3) & (hours < 3 * k)]
    g, l3 = sofar.groupby(sofar.index.normalize()), last3.groupby(last3.index.normalize())
    out = pd.DataFrame({
        "sw_speed_sofar": g["speed"].mean(), "sw_bz_min_sofar": g["bz_gsm"].min(), "sw_vbs_sofar": g["vbs"].mean(),
        "sw_speed_last3": l3["speed"].mean(), "sw_bz_min_last3": l3["bz_gsm"].min(), "sw_vbs_last3": l3["vbs"].mean()})
    enough = g["speed"].count() >= max(1, (3 * k) // 2)
    out[[c for c in out if c.endswith("sofar")]] = out[[c for c in out if c.endswith("sofar")]].where(enough)
    return out


def design(daily: pd.DataFrame, blocks: pd.DataFrame, sw: pd.DataFrame, k: int, lead: int) -> pd.DataFrame:
    """Rows indexed by today D: daily features of issue day D-1 for lead day (lead + 1), plus today's blocks and
    solar wind at update k."""
    base = F.features(daily, lead + 1)
    base.index = base.index + pd.Timedelta(days=1)                # issue day D-1 → today D
    return base.join(block_features(blocks.reindex(base.index), k)).join(sw.reindex(base.index))


def _targets(daily: pd.DataFrame, index, lead: int) -> pd.DataFrame:
    t = daily[config.FORECAST_TARGETS + ["definitive"]].reindex(index + pd.Timedelta(days=lead))
    t.index = index
    return t


def run_year(year: int, daily, blocks, sw_by_k, params) -> pd.DataFrame:
    first = pd.Timestamp(f"{year}-01-01")
    rows = []
    for k in UPDATES:
        for lead in (0, 1):
            X = design(daily, blocks, sw_by_k[k], k, lead)
            y = _targets(daily, X.index, lead)
            target_day = X.index + pd.Timedelta(days=lead)
            today_def = daily["definitive"].reindex(X.index).fillna(False).to_numpy()
            base = ((X.index >= pd.Timestamp(config.FORECAST_TRAIN_START)) & (target_day < first) & today_def
                    & y["definitive"].fillna(False).to_numpy() & X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1).to_numpy()
                    & X["kp_sofar_max"].notna().to_numpy())
            cols = [c for c in X.columns if X.loc[base, c].notna().any()]
            pred_rows = (X.index.year == year) & X["kp_sofar_max"].notna().to_numpy()
            Xp = X.loc[pred_rows, cols]
            out = pd.DataFrame({"today": Xp.index, "k": k, "lead": lead, "target_date": Xp.index + pd.Timedelta(days=lead),
                                "kp_sofar_max": X.loc[pred_rows, "kp_sofar_max"].to_numpy(),
                                "ap_sofar_mean": X.loc[pred_rows, "ap_sofar_mean"].to_numpy()})
            for t in config.FORECAST_TARGETS:
                kk = base & y[t].notna().to_numpy()
                m = gbm._model(params[t]).fit(X.loc[kk, cols], y.loc[kk, t])
                out[t] = np.clip(m.predict(Xp), 0, 400 if t == "ap" else 9)
            kk = base & y["kpmax"].notna().to_numpy()
            c = HistGradientBoostingClassifier(**storm.PARAMS, early_stopping=False, random_state=config.RANDOM_STATE) \
                .fit(X.loc[kk, cols], (y.loc[kk, "kpmax"] >= config.STORM_THRESHOLD).astype(int))
            out["storm_prob"] = c.predict_proba(Xp)[:, 1]
            rows.append(out)
    return pd.concat(rows, ignore_index=True)


def load_inputs():
    daily = load_daily()
    blocks = load_gfz_daily()[KP_COLS].reindex(daily.index)
    hourly = solar_wind_hourly()
    sw_by_k = {k: solar_wind_features(hourly, k) for k in UPDATES}
    return daily, blocks, sw_by_k


def validate() -> pd.DataFrame:
    assert max(YEARS) < config.TEST_START_YEAR, "the test period is not used"
    daily, blocks, sw_by_k = load_inputs()
    params, _ = gbm.load_params()
    OUT.mkdir(parents=True, exist_ok=True)
    frames, t0 = [], time.time()
    print(f"validation: {len(YEARS)} years x {len(UPDATES)} update times x 6 models", flush=True)
    for i, year in enumerate(YEARS, 1):
        frames.append(run_year(year, daily, blocks, sw_by_k, params))
        spent = time.time() - t0
        left = spent / i * (len(YEARS) - i)
        print(f"[{i}/{len(YEARS)}] {year} done | elapsed {spent / 60:.1f} min | about {left / 60:.0f} min left", flush=True)
    fc = pd.concat(frames, ignore_index=True)
    obs = daily.reindex(fc["target_date"])
    fc["ap_obs"], fc["kpmax_obs"] = obs["ap"].to_numpy(), obs["kpmax"].to_numpy()
    fc["obs_definitive"] = obs["definitive"].fillna(False).to_numpy()
    fc.to_csv(OUT / "forecasts.csv", index=False)
    return fc


def _best_threshold(p, y):
    grid = np.round(np.arange(0.02, 0.91, 0.01), 2)
    return max(grid, key=lambda th: scorecard.contingency(p >= th, y)["hss"])


def _hss_far(p, y, th):
    c = scorecard.contingency(p >= th, y)
    return c["hss"], c["far"]


def judge(fc: pd.DataFrame = None) -> dict:
    """Apply the D-72 rule. Today vs the simple rule and the midnight forecast; tomorrow vs the midnight forecast."""
    fc = pd.read_csv(OUT / "forecasts.csv", parse_dates=["today", "target_date"]) if fc is None else fc
    fc = fc[fc["obs_definitive"]]
    mid = pd.read_csv(MIDNIGHT / "forecasts.csv", parse_dates=["target_date"])
    mid_p = pd.read_csv(MIDNIGHT / "storm_probs.csv", parse_dates=["target_date"])
    mid = mid.merge(mid_p[["lead", "target_date", "storm_prob"]], on=["lead", "target_date"])
    mid = mid.assign(lead=mid["lead"] - 1)[["lead", "target_date", "ap", "kpmax", "storm_prob"]]         .rename(columns={"ap": "ap_mid", "kpmax": "kpmax_mid", "storm_prob": "storm_prob_mid"})
    df = fc.merge(mid, on=["lead", "target_date"])            # lead 0 ↔ midnight lead 1, lead 1 ↔ midnight lead 2
    df["year"] = df["target_date"].dt.year
    df["storm"] = df["kpmax_obs"] >= config.STORM_THRESHOLD
    df["kpmax_simple"] = np.maximum(df["kp_sofar_max"], df["kpmax_mid"])
    df["ap_simple"] = (df["ap_sofar_mean"] * df["k"] + df["ap_mid"] * (8 - df["k"])) / 8
    rmse = lambda a, b: float(np.sqrt(np.mean((a - b) ** 2)))  # noqa: E731

    rows = []
    for k in UPDATES:
        t = df[(df["k"] == k) & (df["lead"] == 0)]
        m = df[(df["k"] == k) & (df["lead"] == 1)]
        tune, score = m[m["year"].between(*THRESHOLD_YEARS)], m[m["year"].between(*SCORE_YEARS)]
        th_u, th_m = _best_threshold(tune["storm_prob"], tune["storm"]), _best_threshold(tune["storm_prob_mid"], tune["storm"])
        hss_u, far_u = _hss_far(score["storm_prob"], score["storm"], th_u)
        hss_m, far_m = _hss_far(score["storm_prob_mid"], score["storm"], th_m)
        tt = t[t["year"].between(*THRESHOLD_YEARS)]
        ts = t[t["year"].between(*SCORE_YEARS)]
        th_t, th_tm = _best_threshold(tt["storm_prob"], tt["storm"]), _best_threshold(tt["storm_prob_mid"], tt["storm"])
        rows.append({"update": NAMES[k],
                     "today_kpmax_rmse": rmse(t["kpmax"], t["kpmax_obs"]), "today_kpmax_rmse_simple": rmse(t["kpmax_simple"], t["kpmax_obs"]),
                     "today_kpmax_rmse_midnight": rmse(t["kpmax_mid"], t["kpmax_obs"]),
                     "today_ap_rmse": rmse(t["ap"], t["ap_obs"]), "today_ap_rmse_simple": rmse(t["ap_simple"], t["ap_obs"]),
                     "today_storm_hss": _hss_far(ts["storm_prob"], ts["storm"], th_t)[0],
                     "today_storm_hss_midnight": _hss_far(ts["storm_prob_mid"], ts["storm"], th_tm)[0],
                     "tomorrow_kpmax_rmse": rmse(m["kpmax"], m["kpmax_obs"]), "tomorrow_kpmax_rmse_midnight": rmse(m["kpmax_mid"], m["kpmax_obs"]),
                     "tomorrow_storm_hss": hss_u, "tomorrow_storm_hss_midnight": hss_m,
                     "tomorrow_far": far_u, "tomorrow_far_midnight": far_m})
    table = pd.DataFrame(rows)

    k12 = df[df["k"] == 4]
    years = []
    for y in YEARS:
        m, t = k12[(k12["year"] == y) & (k12["lead"] == 1)], k12[(k12["year"] == y) & (k12["lead"] == 0)]
        years.append({"year": y,
                      "tomorrow_brier": float(np.mean((m["storm_prob"] - m["storm"]) ** 2)),
                      "tomorrow_brier_midnight": float(np.mean((m["storm_prob_mid"] - m["storm"]) ** 2)),
                      "today_kpmax_rmse": rmse(t["kpmax"], t["kpmax_obs"]), "today_kpmax_rmse_simple": rmse(t["kpmax_simple"], t["kpmax_obs"])})
    by_year = pd.DataFrame(years)
    r12 = table.set_index("update").loc["12 UTC"]
    wins_brier = int((by_year["tomorrow_brier"] < by_year["tomorrow_brier_midnight"]).sum())
    wins_today = int((by_year["today_kpmax_rmse"] < by_year["today_kpmax_rmse_simple"]).sum())
    checks = {
        "1 tomorrow storm Heidke at 12 UTC beats midnight": bool(r12["tomorrow_storm_hss"] > r12["tomorrow_storm_hss_midnight"]),
        "2 tomorrow false-alarm ratio at 12 UTC not higher": bool(r12["tomorrow_far"] <= r12["tomorrow_far_midnight"]),
        "3 today max-Kp error below the simple rule at 06, 12, 18 UTC": bool(all(
            table.set_index("update").loc[u, "today_kpmax_rmse"] < table.set_index("update").loc[u, "today_kpmax_rmse_simple"]
            for u in ("06 UTC", "12 UTC", "18 UTC"))),
        f"4 12 UTC wins >= 6/9 years (tomorrow Brier {wins_brier}/9, today max Kp {wins_today}/9)": wins_brier >= 6 and wins_today >= 6,
    }
    table.to_csv(OUT / "summary.csv", index=False)
    by_year.to_csv(OUT / "by_year_12utc.csv", index=False)
    (OUT / "rule.json").write_text(json.dumps({"checks": checks, "passes": all(checks.values())}, indent=2), encoding="utf-8")
    return {"table": table, "by_year": by_year, "checks": checks, "passes": all(checks.values())}


if __name__ == "__main__":
    import sys
    if "--judge" not in sys.argv:
        validate()
    res = judge()
    pd.set_option("display.width", 250)
    print(res["table"].round(3).to_string(index=False))
    print(res["by_year"].round(3).to_string(index=False))
    for name, ok in res["checks"].items():
        print(("PASS " if ok else "FAIL ") + name)
    print("D-72 rule:", "PASSES" if res["passes"] else "FAILS")
