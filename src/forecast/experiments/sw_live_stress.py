"""Stress test (DECISIONS D-69): sw_rec_poisson trained on OMNI, forecasting from degraded (live-like) solar wind.

    python -m src.forecast.experiments.sw_live_stress [output_dir]   # default reports/forecast/experiments/sw_stress

Models are fitted exactly as in validate_yearly (clean OMNI features, targets before each validation year).
Only the prediction rows get degraded solar-wind features. Scenarios:
  clean       OMNI as is (must reproduce validate_yearly's sw_rec_poisson)
  no_archive  27-day echo features blank (the live feed holds 7 days only)
  gaps        random hour dropouts 10%, plasma dropouts 30% in fast/dense hours, 3% whole-day outages
  noise       speed x N(1.02, 0.03), density x 1.25, Bz/By + N(0, 1 nT), |B| + N(0, 0.5 nT) per hour
  worst       no_archive + gaps + noise
  no_sw       every solar-wind feature blank (feed down)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from src import config
from src.daily import load_daily
from src.forecast import gbm, validate_yearly as V

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else config.FORECAST_REPORTS_DIR / "experiments" / "sw_stress"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)


def hourly() -> pd.DataFrame:
    return pd.read_csv(config.PROCESSED_CSV, usecols=["time", "speed", "bz_gsm", "by_gsm", "density", "b_scalar",
                                                      "omni_pressure"], parse_dates=["time"]).set_index("time")


def daily_from(h: pd.DataFrame) -> pd.DataFrame:
    h = h.copy()
    h["bs"] = (-h["bz_gsm"]).clip(lower=0)
    h["vbs"] = h["speed"] * h["bs"] / 1000
    g = h.resample("D")
    d = pd.DataFrame({"sw_speed": g["speed"].mean(), "sw_speed_max": g["speed"].max(), "sw_bz": g["bz_gsm"].mean(),
                      "sw_bz_min": g["bz_gsm"].min(), "sw_vbs": g["vbs"].mean(), "sw_density": g["density"].mean(),
                      "sw_b": g["b_scalar"].mean(), "sw_pressure_max": g["omni_pressure"].max(),
                      "sw_by": g["by_gsm"].mean()})
    return d.where(g["speed"].count() >= 12)


def gaps(h):
    h = h.copy()
    n = len(h)
    h[rng.random(n) < 0.10] = np.nan
    disturbed = ((h["speed"] > 600) | (h["density"] > 15)).to_numpy() & (rng.random(n) < 0.30)
    h.loc[disturbed, ["speed", "density", "omni_pressure"]] = np.nan
    days = h.index.normalize().unique()
    out_days = days[rng.random(len(days)) < 0.03]
    h[h.index.normalize().isin(out_days)] = np.nan
    return h


def noise(h):
    h = h.copy()
    n = len(h)
    h["speed"] *= rng.normal(1.02, 0.03, n)
    h["density"] *= 1.25
    h["omni_pressure"] *= 1.25 * 1.02 ** 2
    h["bz_gsm"] += rng.normal(0, 1.0, n)
    h["by_gsm"] += rng.normal(0, 1.0, n)
    h["b_scalar"] = (h["b_scalar"] + rng.normal(0, 0.5, n)).clip(lower=0)
    return h


REC = ["sw_speed_rec27", "sw_speed_rec27w", "sw_speed_max_rec27", "sw_by_rec27"]


def build(daily, sw_daily, h):
    V.SolarWind._cache = sw_daily
    return V.SolarWindRecPoisson().features(daily, h)


def main():
    daily = load_daily()
    raw = hourly()
    sw = {"clean": daily_from(raw), "gaps": daily_from(gaps(raw)), "noise": daily_from(noise(raw))}
    sw["worst"] = daily_from(noise(gaps(raw)))
    feats = {s: {h: build(daily, d, h) for h in config.FORECAST_LEADS} for s, d in sw.items()}
    sw_cols = [c for c in feats["clean"][1].columns if c.startswith("sw_")]
    feats["no_archive"] = {h: x.assign(**{c: np.nan for c in REC}) for h, x in feats["clean"].items()}
    feats["worst"] = {h: x.assign(**{c: np.nan for c in REC}) for h, x in feats["worst"].items()}
    feats["no_sw"] = {h: x.assign(**{c: np.nan for c in sw_cols}) for h, x in feats["clean"].items()}
    # daily coverage of the solar-wind summaries in the validation years
    for s, d in sw.items():
        d = d.loc["2011":"2019"]
        print(f"{s}: days with solar wind {d['sw_speed'].notna().mean():.3f}", flush=True)

    params, _ = gbm.load_params()
    clf_params = V.Variant().clf_params()
    variant = V.SolarWindRecPoisson()
    scen = list(feats)
    vals = {s: [] for s in scen}
    probs = {s: [] for s in scen}
    ref = daily[config.FORECAST_TARGETS].rolling(config.RECURRENCE_DAYS, min_periods=config.RECURRENCE_DAYS // 2).mean()
    for year in V.YEARS:
        first, last = pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31")
        origins = pd.date_range(first - pd.Timedelta(days=7), last - pd.Timedelta(days=1), freq="D")
        for h in config.FORECAST_LEADS:
            X = feats["clean"][h]
            tgt = daily[config.FORECAST_TARGETS].shift(-h)
            tdate = X.index + pd.Timedelta(days=h)
            tdef = daily["definitive"].reindex(tdate).fillna(False).to_numpy()
            base = (X.index >= config.FORECAST_TRAIN_START) & (tdate < first) & daily["definitive"].to_numpy() & tdef \
                & X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1).to_numpy()
            cols = [c for c in X.columns if X.loc[base, c].notna().any()]
            models = {}
            for t in config.FORECAST_TARGETS:
                k = base & tgt[t].notna().to_numpy()
                models[t] = gbm._model({**params[t], **variant.reg_extra}).fit(X.loc[k, cols], tgt.loc[k, t])
            k = base & tgt["kpmax"].notna().to_numpy()
            y = (tgt.loc[k, "kpmax"] >= config.STORM_THRESHOLD).astype(int)
            clf = HistGradientBoostingClassifier(**clf_params, early_stopping=False,
                                                 random_state=config.RANDOM_STATE).fit(X.loc[k, cols], y)
            for s in scen:
                Xo = feats[s][h].loc[origins, cols]
                out = pd.DataFrame({"origin": origins, "lead": h, "target_date": origins + pd.Timedelta(days=h)})
                for t in config.FORECAST_TARGETS:
                    out[t] = np.clip(models[t].predict(Xo), 0, 400 if t == "ap" else 9)
                    out[f"{t}_ref"] = ref[t].reindex(origins).to_numpy()
                vals[s].append(out.assign(year=year))
                probs[s].append(pd.DataFrame({"origin": origins, "lead": h, "target_date": out["target_date"],
                                              "storm_prob": clf.predict_proba(Xo)[:, 1], "clim": float(y.mean()),
                                              "year": year}))
        print(f"{year} done", flush=True)

    for s in scen:
        v = pd.concat(vals[s], ignore_index=True)
        p = pd.concat(probs[s], ignore_index=True)
        v = v[v.target_date.dt.year == v.year]
        p = p[p.target_date.dt.year == p.year]
        obs = daily.reindex(v["target_date"])
        for t in config.FORECAST_TARGETS:
            v[f"{t}_obs"] = obs[t].to_numpy()
        v = v[obs["definitive"].fillna(False).to_numpy()]
        kp = daily["kpmax"].reindex(p["target_date"])
        p = p.assign(storm_obs=(kp >= config.STORM_THRESHOLD).to_numpy())[kp.notna().to_numpy()]
        d = OUT / s
        d.mkdir(exist_ok=True)
        v.to_csv(d / "forecasts.csv", index=False)
        p.to_csv(d / "storm_probs.csv", index=False)

    V.OUT = OUT
    base_dir = config.FORECAST_REPORTS_DIR / "experiments" / "yearly" / "baseline"
    (OUT / "baseline").mkdir(exist_ok=True)
    for f in ("forecasts.csv", "storm_probs.csv"):
        (OUT / "baseline" / f).write_bytes((base_dir / f).read_bytes())
    b = V.summarise("baseline")
    rows = []
    for s in ["baseline"] + scen:
        r = b if s == "baseline" else V.summarise(s)
        row = {"scenario": s}
        for t in config.FORECAST_TARGETS:
            row[f"{t}_skill"] = r[f"{t}_skill"]
            row[f"{t}_wins"] = sum(r[f"{t}_skill_by_year"][y] > b[f"{t}_skill_by_year"][y] for y in V.YEARS)
            row[f"{t}_rmse_d1"] = r[f"{t}_rmse_d1"]
        row.update(hss_d1=r["hss_d1"], hss_d1_3=r["hss_d1_3"], brier_skill=r["brier_skill"])
        rows.append(row)
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "summary.csv", index=False)
    pd.set_option("display.width", 250)
    print(t.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
