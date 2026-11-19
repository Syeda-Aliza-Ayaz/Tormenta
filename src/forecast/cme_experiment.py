"""Experiment: do CME catalogue features improve HistGB and the storm classifier? (DECISIONS D-67, option A)

CME features come from NASA DONKI (src/ingest/fetch_donki.py) and use only what was in the catalogue when the
forecast was issued: an entry counts for issue day D only if it was submitted by the end of D, and an arrival
prediction only if its model run had completed by then. DONKI is kept in real time from April 2014 (before that,
entries were added months or years later), so the features are blank (NaN) before REALTIME_START.

Features (per issue day D; blank before REALTIME_START):
  cme_fast3        CMEs of the last 3 days with speed >= 800 km/s
  cme_maxspeed3    fastest CME of the last 3 days (km/s; 0 when none)
  cme_wide3        last-3-day CMEs at least 45° half-angle within 60° of the Sun's centre line (Earth-facing)
Per lead day h (target day D+h):
  cme_arrive       Earth arrivals predicted for the target day by the arrival model (WSA-ENLIL)
  cme_arrive_pm1   predicted arrivals within one day of the target day
  cme_arrive_kp    highest Kp predicted for those arrivals (0 when none)

Raw CME counts are not used: the number of small CMEs logged per year rose sharply after 2021 (logging practice).

Each variant trains to 2022-12-31 with the settings already chosen for it in the start-year experiment (D-66), with
and without CME features, so the only difference is the CME features. Storm thresholds come from out-of-fold
probabilities (5 time-ordered folds, 7-day gap). Test: 2023-01-01 → last definitive day. No live file is touched.

    python -m src.forecast.cme_experiment
"""
import json

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from src import config
from src.daily import load_daily
from src.forecast import features as F, gbm, storm
from src.forecast.baselines import TrailingMean
from src.forecast.start_year import TEST_START, rows_from
from src.forecast.start_year import score as score_values
from src.ingest.fetch_donki import load_table

REALTIME_START = pd.Timestamp("2014-04-01")
VARIANTS = [1947, 2010]
OUT = config.FORECAST_REPORTS_DIR / "experiments" / "cme"
SETTINGS = config.FORECAST_REPORTS_DIR / "experiments" / "start_year" / "summary.csv"


def cme_features(days: pd.DatetimeIndex) -> tuple:
    """(base features by issue day, {h: lead features by issue day}) using only entries known by the end of each day."""
    cat = load_table()
    base, lead = [], {h: [] for h in config.FORECAST_LEADS}
    for d in days:
        if d < REALTIME_START:
            continue
        cutoff = d + pd.Timedelta(days=1)
        known = cat[cat["submitted"] < cutoff]
        recent = known[(known["start"] >= d - pd.Timedelta(days=2)) & (known["start"] < cutoff)]
        measured = recent[recent["analysis_submitted"] < cutoff]
        speed = measured["speed"].fillna(0)
        wide = (measured["half_angle"].fillna(0) >= 45) & (measured["longitude"].abs() <= 60)
        base.append({"date": d, "cme_fast3": int((speed >= 800).sum()), "cme_maxspeed3": float(speed.max()) if len(speed) else 0.0,
                     "cme_wide3": int(wide.sum())})
        preds = known[(known["arrival_model_done"] < cutoff) & known["predicted_arrival"].notna()]
        arrive_day = preds["predicted_arrival"].dt.normalize()
        for h in config.FORECAST_LEADS:
            target = d + pd.Timedelta(days=h)
            on = preds[arrive_day == target]
            near = preds[(arrive_day >= target - pd.Timedelta(days=1)) & (arrive_day <= target + pd.Timedelta(days=1))]
            lead[h].append({"date": d, "cme_arrive": len(on), "cme_arrive_pm1": len(near),
                            "cme_arrive_kp": float(on["predicted_kp_90"].max()) if on["predicted_kp_90"].notna().any() else 0.0})
    base = pd.DataFrame(base).set_index("date").reindex(days)
    lead = {h: pd.DataFrame(v).set_index("date").reindex(days) for h, v in lead.items()}
    return base, lead


class Model:
    """HistGB regressors (Ap, max Kp) and storm classifiers per lead day, optionally with CME features."""

    def __init__(self, params: dict, cme=None):
        self.params, self.cme = params, cme

    def X(self, frame: pd.DataFrame, h: int, index) -> pd.DataFrame:
        x = F.features(frame, h).reindex(index)
        if self.cme is not None:
            base, lead = self.cme
            x = x.join(base.reindex(index)).join(lead[h].reindex(index))
        return x

    def fit(self, rows: pd.DataFrame):
        self.reg, self.clf, self.cols = {}, {}, {}
        for h in config.FORECAST_LEADS:
            x, y = self.X(rows, h, rows.index), F.targets(rows, h)
            keep = x[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1) & ~rows["lead_in"]
            # a fold that ends before REALTIME_START has no CME values at all: those columns are left out
            self.cols[h] = [c for c in x.columns if x.loc[keep, c].notna().any()]
            x = x[self.cols[h]]
            for t in config.FORECAST_TARGETS:
                k = keep & y[t].notna()
                self.reg[(h, t)] = gbm._model(self.params[t]).fit(x[k], y.loc[k, t])
            k = keep & y["kpmax"].notna()
            self.clf[h] = HistGradientBoostingClassifier(**storm.PARAMS, early_stopping=False,
                                                         random_state=config.RANDOM_STATE).fit(
                x[k], (y.loc[k, "kpmax"] >= config.STORM_THRESHOLD).astype(int))
        return self

    def predict(self, daily: pd.DataFrame, origins: pd.DatetimeIndex) -> tuple:
        window = daily.loc[origins.min() - pd.Timedelta(days=config.FORECAST_HISTORY_DAYS): origins.max()]
        vals, probs = [], []
        for h in config.FORECAST_LEADS:
            x = self.X(window, h, origins)[self.cols[h]]
            tgt = origins + pd.Timedelta(days=h)
            vals.append(pd.DataFrame({"origin": origins, "lead": h, "target_date": tgt,
                                      **{t: self.reg[(h, t)].predict(x) for t in config.FORECAST_TARGETS}}))
            probs.append(pd.DataFrame({"origin": origins, "lead": h, "target_date": tgt,
                                       "storm_prob": self.clf[h].predict_proba(x)[:, 1]}))
        return pd.concat(vals, ignore_index=True), pd.concat(probs, ignore_index=True)


def thresholds_oof(rows, daily, params, cme) -> dict:
    x, _ = gbm._xy(rows, 3, "ap")
    parts = []
    for tr, te in gbm.cv_folds(x):
        first, last = x.index[te][0], x.index[te][-1]
        m = Model(params, cme).fit(rows.loc[: x.index[tr][-1]])
        _, p = m.predict(daily, pd.date_range(first - pd.Timedelta(days=7), last, freq="D"))
        p = storm.attach_obs(p, daily)
        parts.append(p[p["target_date"].between(first, last)])
    return storm.tune_thresholds(pd.concat(parts, ignore_index=True))


def score(vals, probs, thresholds, ref, daily, test_end) -> tuple:
    keep = lambda f: f[f["target_date"].between(TEST_START, test_end)]  # noqa: E731
    lt = score_values(keep(vals), keep(ref), daily)
    p = storm.attach_obs(keep(probs), daily)
    p = p[p["obs_definitive"]].assign(threshold=lambda d: d["lead"].map(thresholds))
    p["warning"] = p["storm_prob"] >= p["threshold"]
    return lt, storm.table(p)


def main():
    daily = load_daily()
    test_end = daily.index[daily["definitive"]].max()
    print("building CME features (known-at-the-time only)…")
    cme = cme_features(daily.index[daily.index >= REALTIME_START - pd.Timedelta(days=1)])
    origins = pd.date_range(TEST_START - pd.Timedelta(days=7), test_end - pd.Timedelta(days=1), freq="D")
    ref = TrailingMean().predict(daily, origins)
    settings = pd.read_csv(SETTINGS).set_index("start")
    OUT.mkdir(parents=True, exist_ok=True)
    summary, leads, storms = [], [], []
    for start in VARIANTS:
        rows = rows_from(daily, start)
        params = json.loads(settings.loc[start, "params"])
        for with_cme in (False, True):
            c = cme if with_cme else None
            th = thresholds_oof(rows, daily, params, c)
            vals, probs = Model(params, c).fit(rows).predict(daily, origins)
            lt, st = score(vals, probs, th, ref, daily, test_end)
            name = f"{start}{' + CME' if with_cme else ''}"
            leads.append(lt.assign(variant=name)); storms.append(st.assign(variant=name))
            summary.append({"variant": name, "ap_skill": lt[lt.target == "ap"]["skill_vs_trailing27"].mean(),
                            "kp_skill": lt[lt.target == "kpmax"]["skill_vs_trailing27"].mean(),
                            "ap_rmse_d1": lt[(lt.target == "ap") & (lt.lead == 1)]["rmse"].iloc[0],
                            "hss_d1": st[st.lead == 1]["hss"].iloc[0], "hss_d1_3": st[st.lead <= 3]["hss"].mean(),
                            "hss_mean": st["hss"].mean(), "pod_d1": st[st.lead == 1]["pod"].iloc[0],
                            "far_d1": st[st.lead == 1]["far"].iloc[0], "brier": st["brier"].mean(),
                            "thresholds": json.dumps(th)})
            s = summary[-1]
            print(f"{name:12s} Ap skill {s['ap_skill']:+.3f} | Kp skill {s['kp_skill']:+.3f} | storm Heidke day1 {s['hss_d1']:.3f} "
                  f"days1-3 {s['hss_d1_3']:.3f} | Brier {s['brier']:.4f}")
    pd.DataFrame(summary).to_csv(OUT / "summary.csv", index=False)
    pd.concat(leads).to_csv(OUT / "test_leads.csv", index=False)
    pd.concat(storms).to_csv(OUT / "test_storms.csv", index=False)
    cme[0].join(pd.concat({h: v.add_suffix(f"_d{h}") for h, v in cme[1].items()}, axis=1).droplevel(0, axis=1)).to_csv(OUT / "cme_features.csv")
    print(f"results in {OUT}")


if __name__ == "__main__":
    main()
