"""Experiment: does a shorter, more recent training history help? (DECISIONS D-66)

Each variant trains HistGB and the storm classifier on definitive days from its start year to 2022-12-31 and is scored
on 2023-01-01 → the last definitive day, which no variant saw. Everything is chosen inside each variant's own training
years with 5 time-ordered folds and a 7-day gap: HistGB settings by CV RMSE (lead day 3), storm thresholds by Heidke
skill on the folds' out-of-sample probabilities. Features may read history before the start year (lead-in, D-59);
only the training rows start there.

This changes no live model, app file or earlier result.

    python -m src.forecast.experiments.start_year
"""
import json

import numpy as np
import pandas as pd

from src import config
from src.daily import load_daily
from src.forecast import gbm, storm
from src.forecast.baselines import TrailingMean

STARTS = [1947, 1980, 1995, 2010]
TRAIN_END = pd.Timestamp("2022-12-31")
TEST_START = pd.Timestamp("2023-01-01")
OUT = config.FORECAST_REPORTS_DIR / "experiments" / "start_year"
N_ITER = 12


def rows_from(daily: pd.DataFrame, start_year: int) -> pd.DataFrame:
    """Definitive days from the start year to TRAIN_END, with lead-in history flagged as in training_rows (D-59)."""
    start = max(pd.Timestamp(f"{start_year}-01-01"), pd.Timestamp(config.FORECAST_TRAIN_START))
    rows = daily.loc[start - pd.Timedelta(days=config.FORECAST_HISTORY_DAYS): TRAIN_END]
    rows = rows[rows["definitive"]]
    return rows.assign(lead_in=rows.index < start)


def fold_scores(rows: pd.DataFrame, params: dict, target: str) -> list:
    X, y = gbm._xy(rows, 3, target)
    ref = X["ap_mean27" if target == "ap" else "kpmax_mean27"]
    out = []
    for i, (tr, te) in enumerate(gbm.cv_folds(X), 1):
        p = gbm._model(params).fit(X.iloc[tr], y.iloc[tr]).predict(X.iloc[te])
        yt = y.iloc[te].to_numpy()
        rmse = float(np.sqrt(np.mean((p - yt) ** 2)))
        r = float(np.sqrt(np.mean((ref.iloc[te].to_numpy() - yt) ** 2)))
        out.append({"fold": i, "train_from": str(X.index[tr][0].date()), "train_to": str(X.index[tr][-1].date()),
                    "check_from": str(X.index[te][0].date()), "check_to": str(X.index[te][-1].date()),
                    "rmse": rmse, "ref_rmse": r, "skill": 1 - (rmse / r) ** 2})
    return out


def oof_thresholds(rows: pd.DataFrame, daily: pd.DataFrame) -> dict:
    """Storm thresholds from the classifier's out-of-fold probabilities, folds as in tuning (lead day 3 rows)."""
    X, _ = gbm._xy(rows, 3, "ap")
    parts = []
    for tr, te in gbm.cv_folds(X):
        fit_rows = rows.loc[: X.index[tr][-1]]
        first, last = X.index[te][0], X.index[te][-1]
        model = storm.StormClassifier().fit(fit_rows)
        origins = pd.date_range(first - pd.Timedelta(days=7), last, freq="D")
        fc = storm.attach_obs(model.predict(daily, origins), daily)
        parts.append(fc[fc["target_date"].between(first, last)])
    return storm.tune_thresholds(pd.concat(parts, ignore_index=True))


def score(fc: pd.DataFrame, ref: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Errors of fc and of the 27-day reference on the same (issue day, lead day) pairs, matched by key."""
    m = fc.merge(ref, on=["origin", "lead", "target_date"], suffixes=("", "_ref"))
    obs = daily.reindex(m["target_date"])
    rows = []
    for t in config.FORECAST_TARGETS:
        g = m.assign(o=obs[t].to_numpy()).dropna(subset=["o"])
        for h in config.FORECAST_LEADS:
            gh = g[g["lead"] == h]
            e = (gh[t] - gh["o"]).to_numpy()
            er = (gh[f"{t}_ref"] - gh["o"]).to_numpy()
            rows.append({"target": t, "lead": h, "n": len(e), "rmse": float(np.sqrt(np.mean(e ** 2))),
                         "mae": float(np.mean(np.abs(e))), "skill_vs_trailing27": 1 - np.mean(e ** 2) / np.mean(er ** 2)})
    return pd.DataFrame(rows)


def main() -> dict:
    daily = load_daily()
    test_end = daily.index[daily["definitive"]].max()
    origins = pd.date_range(TEST_START - pd.Timedelta(days=7), test_end - pd.Timedelta(days=1), freq="D")
    keep = lambda fc: fc[fc["target_date"].between(TEST_START, test_end)]  # noqa: E731
    ref = keep(TrailingMean().predict(daily, origins))
    OUT.mkdir(parents=True, exist_ok=True)
    summary, folds, leads, storms = [], [], [], []
    for start in STARTS:
        rows = rows_from(daily, start)
        n_train = int((~rows["lead_in"]).sum())
        params = {}
        for target in config.FORECAST_TARGETS:
            best, _ = gbm.tune(rows, target, n_iter=N_ITER)
            params[target] = best
            folds += [{"start": start, "target": target, **f} for f in fold_scores(rows, best, target)]
        model = gbm.HistGBDirect(params).fit(rows)
        lt = score(keep(model.predict(daily, origins)), ref, daily).assign(start=start)
        leads.append(lt)
        thresholds = oof_thresholds(rows, daily)
        warn = storm.StormClassifier().fit(rows)
        warn.thresholds_ = thresholds
        w = storm.attach_obs(warn.predict(daily, origins), daily)
        st = storm.table(w[w["target_date"].between(TEST_START, test_end) & w["obs_definitive"]]).assign(start=start)
        storms.append(st)
        storm_rate = float((rows.loc[~rows["lead_in"], "kpmax"] >= config.STORM_THRESHOLD).mean())
        summary.append({"start": start, "train_days": n_train, "train_storm_rate": storm_rate,
                        "ap_skill_1to7": float(lt[lt.target == "ap"]["skill_vs_trailing27"].mean()),
                        "kp_skill_1to7": float(lt[lt.target == "kpmax"]["skill_vs_trailing27"].mean()),
                        "ap_rmse_day1": float(lt[(lt.target == "ap") & (lt.lead == 1)]["rmse"].iloc[0]),
                        "kp_rmse_day1": float(lt[(lt.target == "kpmax") & (lt.lead == 1)]["rmse"].iloc[0]),
                        "storm_hss_day1": float(st[st.lead == 1]["hss"].iloc[0]), "storm_hss_mean": float(st["hss"].mean()),
                        "storm_pod_day1": float(st[st.lead == 1]["pod"].iloc[0]), "brier_mean": float(st["brier"].mean()),
                        "params": json.dumps(params), "thresholds": json.dumps(thresholds)})
        print(f"start {start}: {n_train:,} training days, Ap skill {summary[-1]['ap_skill_1to7']:+.3f}, "
              f"storm Heidke day 1 {summary[-1]['storm_hss_day1']:.3f}")
    pd.DataFrame(summary).to_csv(OUT / "summary.csv", index=False)
    pd.DataFrame(folds).to_csv(OUT / "folds.csv", index=False)
    pd.concat(leads).to_csv(OUT / "test_leads.csv", index=False)
    pd.concat(storms).to_csv(OUT / "test_storms.csv", index=False)
    print(f"test 2023-01-01 -> {test_end.date()}: results in {OUT}")
    return {"summary": pd.DataFrame(summary)}


if __name__ == "__main__":
    main()
