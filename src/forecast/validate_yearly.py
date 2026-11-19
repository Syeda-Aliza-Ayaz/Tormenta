"""Yearly validation for changes to the forecaster (DECISIONS D-68). The test period (2020 →) is never read.

For each validation year Y in 2011–2019: train on definitive days from FORECAST_TRAIN_START whose target day is
before Y-01-01, then forecast every day of Y from data up to each issue day. Nine years, 362 storm days, across a
full solar cycle. Model settings stay as they are (histgb_params.json, storm.PARAMS), so a variant differs from the
baseline only by the change it tests.

Storm thresholds are chosen on the 2011–2014 forecasts (Heidke, per lead day) and the Heidke score is reported on
2015–2019. Brier skill and average precision (area under the precision-recall curve) need no threshold and use all
nine years.

Rule, fixed before any run (D-68). A change is kept only if
  1. the pooled skill over the validation years improves (Ap; max Kp for Kp-targeted changes),
  2. it wins in at least two thirds of the years it is judged on (6 of 9; CME: 2015–2019, 4 of 5),
  3. the storm Heidke score for lead days 1–3 (2015–2019) does not drop by more than 0.01.

    python -m src.forecast.validate_yearly --check                  # harness check: 2017–2019 block = D-63 validation
    python -m src.forecast.validate_yearly baseline poisson log_ap  # run variants, then compare with the baseline
    python -m src.forecast.validate_yearly --compare                # compare saved variants only
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, log_loss
from sklearn.model_selection import ParameterSampler

from src import config, scorecard
from src.daily import load_daily
from src.forecast import features as F, gbm, storm
from src.ingest import sw_archive

YEARS = list(range(2011, 2020))
THRESHOLD_YEARS = (2011, 2014)
CME_YEARS = list(range(2015, 2020))
CME_LEADS = (1, 2, 3)
OUT = config.FORECAST_REPORTS_DIR / "experiments" / "yearly"
STORM_TUNE_END = pd.Timestamp("2010-12-31")      # classifier settings are chosen on data before every validation year


# ── variants ──────────────────────────────────────────────────────────────────────────────────────────────────
class Variant:
    """Baseline: the live feature set, live HistGB settings, live classifier settings."""
    name = "baseline"
    years = YEARS
    reg_extra: dict = {}
    log_ap = False

    def features(self, daily: pd.DataFrame, h: int) -> pd.DataFrame:
        return F.features(daily, h)

    def clf_params(self) -> dict:
        return storm.PARAMS


class Poisson(Variant):
    name = "poisson"
    reg_extra = {"loss": "poisson"}


class LogAp(Variant):
    name = "log_ap"
    log_ap = True


class StormTuned(Variant):
    name = "storm_tuned"

    def clf_params(self) -> dict:
        return tune_storm_params()


class Cme(Variant):
    """CME catalogue features (D-67, known at issue time) on lead days 1–3 only."""
    name = "cme"
    years = CME_YEARS
    _cache = None

    def features(self, daily, h):
        x = F.features(daily, h)
        if h not in CME_LEADS:
            return x
        if Cme._cache is None:
            from src.forecast.cme_experiment import REALTIME_START, cme_features
            days = daily.index[(daily.index >= REALTIME_START - pd.Timedelta(days=1)) & (daily.index.year < config.TEST_START_YEAR)]
            Cme._cache = cme_features(days)
        base, lead = Cme._cache
        return x.join(base.reindex(x.index)).join(lead[h].reindex(x.index))


def solar_wind_daily() -> pd.DataFrame:
    """Daily solar-wind summaries (UTC days) from the hourly OMNI table, 1998 onward, with the same definition the
    live archive uses (sw_archive.daily_summary). Day D is complete by the end of D, when the forecast is issued."""
    h = pd.read_csv(config.PROCESSED_CSV, usecols=["time", *sw_archive.COLUMNS], parse_dates=["time"]).set_index("time")
    return sw_archive.daily_summary(h)


class SolarWind(Variant):
    """Solar wind of the issue day and the day before (OMNI, 1998 onward; blank before)."""
    name = "solar_wind"
    _cache = None
    COLS = ["sw_speed", "sw_speed_max", "sw_bz", "sw_bz_min", "sw_vbs", "sw_density", "sw_b", "sw_pressure_max"]

    def sw(self, index) -> pd.DataFrame:
        if SolarWind._cache is None:
            SolarWind._cache = solar_wind_daily()
        return SolarWind._cache.reindex(index)

    def features(self, daily, h):
        sw = self.sw(daily.index)
        x = F.features(daily, h)
        for c in self.COLS:
            x[f"{c}_lag0"] = sw[c]
        for c in ("sw_speed", "sw_vbs"):
            x[f"{c}_lag1"] = sw[c].shift(1)
        x["sw_speed_change"] = sw["sw_speed"] - sw["sw_speed"].shift(1)
        return x


class SolarWindRec(SolarWind):
    """Plus the 27-day echo of fast streams and the field direction one rotation before the target day (the
    sector structure recurs; with the target-day season it carries the Russell–McPherron effect)."""
    name = "solar_wind_rec"

    def features(self, daily, h):
        x = super().features(daily, h)
        sw = self.sw(daily.index)
        r = config.RECURRENCE_DAYS
        x["sw_speed_rec27"] = sw["sw_speed"].shift(r - h)
        x["sw_speed_rec27w"] = pd.concat([sw["sw_speed"].shift(r - h + d) for d in (-1, 0, 1)], axis=1).mean(axis=1)
        x["sw_speed_max_rec27"] = sw["sw_speed_max"].shift(r - h)
        x["sw_by_rec27"] = sw["sw_by"].shift(r - h)
        x["sw_by_lag0"] = sw["sw_by"]
        return x


class SolarWindRecPoisson(SolarWindRec):
    """Combination of the variants that passed alone: solar wind with the 27-day echo, Poisson loss."""
    name = "sw_rec_poisson"
    reg_extra = {"loss": "poisson"}


class SolarWindRecPoissonCme(SolarWindRecPoisson):
    """The same plus CME features on lead days 1–3, judged on 2015–2019 like the CME variant."""
    name = "sw_rec_poisson_cme"
    years = CME_YEARS

    def features(self, daily, h):
        x = super().features(daily, h)
        if h not in CME_LEADS:
            return x
        c = Cme().features(daily, h)
        return x.join(c[[k for k in c.columns if k.startswith("cme_")]])


VARIANTS = {v.name: v for v in (Variant, Poisson, LogAp, StormTuned, Cme, SolarWind, SolarWindRec,
                                SolarWindRecPoisson, SolarWindRecPoissonCme)}


# ── storm classifier settings, chosen on data before 2011 ─────────────────────────────────────────────────────
def tune_storm_params(n_iter: int = 12, h: int = 3) -> dict:
    path = OUT / "storm_params.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["params"]
    daily = load_daily()
    X = F.features(daily, h)
    kp = daily["kpmax"].shift(-h)
    keep = (X.index >= config.FORECAST_TRAIN_START) & (X.index + pd.Timedelta(days=h) <= STORM_TUNE_END) \
        & kp.notna() & X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1)
    X, y = X[keep], (kp[keep] >= config.STORM_THRESHOLD).astype(int)
    rows = []
    for params in ParameterSampler(gbm.SEARCH_SPACE, n_iter=n_iter, random_state=config.RANDOM_STATE):
        params = {k: (int(v) if k in ("max_iter", "max_leaf_nodes", "min_samples_leaf") else float(v)) for k, v in params.items()}
        losses = []
        for tr, te in gbm.cv_folds(X):
            p = HistGradientBoostingClassifier(**params, early_stopping=False, random_state=config.RANDOM_STATE) \
                .fit(X.iloc[tr], y.iloc[tr]).predict_proba(X.iloc[te])[:, 1]
            losses.append(log_loss(y.iloc[te], p, labels=[0, 1]))
        rows.append({**params, "cv_log_loss": float(np.mean(losses))})
    table = pd.DataFrame(rows).sort_values("cv_log_loss", ignore_index=True)
    live = []
    for tr, te in gbm.cv_folds(X):
        p = HistGradientBoostingClassifier(**storm.PARAMS, early_stopping=False, random_state=config.RANDOM_STATE) \
            .fit(X.iloc[tr], y.iloc[tr]).predict_proba(X.iloc[te])[:, 1]
        live.append(log_loss(y.iloc[te], p, labels=[0, 1]))
    best = {k: (int(v) if k in ("max_iter", "max_leaf_nodes", "min_samples_leaf") else float(v))
            for k, v in table.iloc[0].drop("cv_log_loss").items()}
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "storm_tuning.csv", index=False)
    path.write_text(json.dumps({"params": best, "cv_log_loss": float(table["cv_log_loss"].iloc[0]),
                                "live_params_cv_log_loss": float(np.mean(live)),
                                "tuned_on": f"{config.FORECAST_TRAIN_START} -> {STORM_TUNE_END.date()}"}, indent=2),
                    encoding="utf-8")
    print(f"storm classifier: tuned log loss {table['cv_log_loss'].iloc[0]:.4f} vs live settings {np.mean(live):.4f}")
    return best


# ── one block: fit on targets before `first`, forecast target days first..last ────────────────────────────────
def run_block(variant: Variant, daily: pd.DataFrame, feats: dict, params: dict, clf_params: dict,
              first: pd.Timestamp, last: pd.Timestamp) -> tuple:
    assert last.year < config.TEST_START_YEAR, "the test period is not used for validation"
    origins = pd.date_range(first - pd.Timedelta(days=max(config.FORECAST_LEADS)), last - pd.Timedelta(days=1), freq="D")
    ref = daily[config.FORECAST_TARGETS].rolling(config.RECURRENCE_DAYS, min_periods=config.RECURRENCE_DAYS // 2).mean()
    vals, probs = [], []
    for h in config.FORECAST_LEADS:
        X = feats[h]
        tgt = daily[config.FORECAST_TARGETS].shift(-h)
        tdate = X.index + pd.Timedelta(days=h)
        tdef = daily["definitive"].reindex(tdate).fillna(False).to_numpy()
        base = (X.index >= config.FORECAST_TRAIN_START) & (tdate < first) & daily["definitive"].to_numpy() & tdef \
            & X[["ap_lag0", "kpmax_lag0"]].notna().all(axis=1).to_numpy()
        cols = [c for c in X.columns if X.loc[base, c].notna().any()]   # e.g. CME columns before 2014
        Xo = X.loc[origins, cols]
        out = pd.DataFrame({"origin": origins, "lead": h, "target_date": origins + pd.Timedelta(days=h)})
        for t in config.FORECAST_TARGETS:
            k = base & tgt[t].notna().to_numpy()
            y = tgt.loc[k, t]
            log = t == "ap" and variant.log_ap
            m = gbm._model({**params[t], **variant.reg_extra}).fit(X.loc[k, cols], np.log1p(y) if log else y)
            p = m.predict(Xo)
            out[t] = np.clip(np.expm1(p) if log else p, 0, 400 if t == "ap" else 9)
            out[f"{t}_ref"] = ref[t].reindex(origins).to_numpy()
        vals.append(out)
        k = base & tgt["kpmax"].notna().to_numpy()
        y = (tgt.loc[k, "kpmax"] >= config.STORM_THRESHOLD).astype(int)
        c = HistGradientBoostingClassifier(**clf_params, early_stopping=False, random_state=config.RANDOM_STATE) \
            .fit(X.loc[k, cols], y)
        probs.append(pd.DataFrame({"origin": origins, "lead": h, "target_date": origins + pd.Timedelta(days=h),
                                   "storm_prob": c.predict_proba(Xo)[:, 1], "clim": float(y.mean())}))
    keep = lambda f: f[f["target_date"].between(first, last)]  # noqa: E731
    vals, probs = keep(pd.concat(vals, ignore_index=True)), keep(pd.concat(probs, ignore_index=True))
    obs = daily.reindex(vals["target_date"])
    for t in config.FORECAST_TARGETS:
        vals[f"{t}_obs"] = obs[t].to_numpy()
    vals = vals[obs["definitive"].fillna(False).to_numpy()]
    kp = daily["kpmax"].reindex(probs["target_date"])
    probs = probs.assign(storm_obs=(kp >= config.STORM_THRESHOLD).to_numpy())[kp.notna().to_numpy()]
    return vals, probs


def run_variant(name: str, daily: pd.DataFrame) -> None:
    variant = VARIANTS[name]()
    params, _ = gbm.load_params()
    clf_params = variant.clf_params()
    feats = {h: variant.features(daily, h) for h in config.FORECAST_LEADS}
    vals, probs = [], []
    for year in YEARS:
        v, p = run_block(variant, daily, feats, params, clf_params,
                         pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31"))
        vals.append(v.assign(year=year)); probs.append(p.assign(year=year))
        print(f"  {name} {year}: done", flush=True)
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    pd.concat(vals).to_csv(d / "forecasts.csv", index=False)
    pd.concat(probs).to_csv(d / "storm_probs.csv", index=False)


# ── scoring ───────────────────────────────────────────────────────────────────────────────────────────────────
def value_scores(vals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t in config.FORECAST_TARGETS:
        g = vals.dropna(subset=[f"{t}_obs"])
        e, er = g[t] - g[f"{t}_obs"], g[f"{t}_ref"] - g[f"{t}_obs"]
        for (year, h), idx in g.groupby(["year", "lead"]).groups.items():
            rows.append({"target": t, "year": year, "lead": h, "n": len(idx), "sse": float((e[idx] ** 2).sum()),
                         "sse_ref": float((er[idx] ** 2).sum()), "sae": float(e[idx].abs().sum())})
    return pd.DataFrame(rows)


def summarise(name: str) -> dict:
    d = OUT / name
    vals = pd.read_csv(d / "forecasts.csv", parse_dates=["origin", "target_date"])
    probs = pd.read_csv(d / "storm_probs.csv", parse_dates=["origin", "target_date"])
    s = value_scores(vals)
    out = {"variant": name}
    for t in config.FORECAST_TARGETS:
        g = s[s.target == t]
        pooled = g.groupby("lead")[["sse", "sse_ref", "sae", "n"]].sum()
        out[f"{t}_skill"] = float((1 - pooled.sse / pooled.sse_ref).mean())
        out[f"{t}_rmse_d1"] = float(np.sqrt(pooled.sse[1] / pooled.n[1]))
        out[f"{t}_mae_d1"] = float(pooled.sae[1] / pooled.n[1])
        by_year = g.groupby(["year", "lead"])[["sse", "sse_ref"]].sum()
        out[f"{t}_skill_by_year"] = (1 - by_year.sse / by_year.sse_ref).groupby("year").mean().to_dict()
    lo, hi = THRESHOLD_YEARS
    th = storm.tune_thresholds(probs[probs.year.between(lo, hi)])
    late = probs[probs.year > hi]
    hss = {}
    for h, g in late.groupby("lead"):
        hss[int(h)] = scorecard.contingency(g["storm_prob"] >= th[int(h)], g["storm_obs"])["hss"]
    bss, ap_score = {}, {}
    for h, g in probs.groupby("lead"):
        bss[int(h)] = 1 - np.mean((g.storm_prob - g.storm_obs) ** 2) / np.mean((g.clim - g.storm_obs) ** 2)
        ap_score[int(h)] = average_precision_score(g.storm_obs, g.storm_prob)
    out.update({"hss_d1": hss[1], "hss_d1_3": float(np.mean([hss[h] for h in (1, 2, 3)])),
                "hss_mean": float(np.mean(list(hss.values()))), "brier_skill": float(np.mean(list(bss.values()))),
                "avg_precision": float(np.mean(list(ap_score.values()))),
                "brier_skill_d1_3": float(np.mean([bss[h] for h in (1, 2, 3)])),
                "thresholds": json.dumps(th)})
    return out


def compare(names: list) -> pd.DataFrame:
    rows = {n: summarise(n) for n in names if (OUT / n / "forecasts.csv").exists()}
    if "baseline" not in rows:
        raise SystemExit("run the baseline first")
    b = rows["baseline"]
    table = []
    for n, r in rows.items():
        years = VARIANTS[n].years
        row = {k: v for k, v in r.items() if not k.endswith("_by_year")}
        for t in config.FORECAST_TARGETS:
            wins = sum(r[f"{t}_skill_by_year"][y] > b[f"{t}_skill_by_year"][y] for y in years)
            row[f"{t}_wins"] = f"{wins}/{len(years)}"
            row[f"{t}_skill_gain"] = r[f"{t}_skill"] - b[f"{t}_skill"]
        need = -(-2 * len(years) // 3)
        row["hss_d1_3_change"] = r["hss_d1_3"] - b["hss_d1_3"]
        if n != "baseline":
            ok = {t: row[f"{t}_skill_gain"] > 0 and int(row[f"{t}_wins"].split("/")[0]) >= need
                  for t in config.FORECAST_TARGETS}
            row["passes_rule"] = (ok["ap"] or ok["kpmax"]) and row["hss_d1_3_change"] >= -0.01
        table.append(row)
    table = pd.DataFrame(table)
    table.to_csv(OUT / "summary.csv", index=False)
    by_year = pd.DataFrame({n: rows[n]["ap_skill_by_year"] for n in rows})
    by_year.to_csv(OUT / "ap_skill_by_year.csv")
    return table


def check(daily: pd.DataFrame) -> None:
    """The harness on the D-63 validation block (fit ≤ 2016, forecast 2017–2019) must give the saved validation RMSE."""
    params, _ = gbm.load_params()
    v = Variant()
    feats = {h: v.features(daily, h) for h in config.FORECAST_LEADS}
    vals, _ = run_block(v, daily, feats, params, storm.PARAMS, pd.Timestamp("2017-01-01"), pd.Timestamp("2019-12-31"))
    saved = pd.read_csv(config.FORECAST_REPORTS_DIR / "metrics" / "validation_leads.csv")
    saved = saved[saved.model == "histgb"].set_index(["target", "lead"])["rmse"]
    for t in config.FORECAST_TARGETS:
        for h in config.FORECAST_LEADS:
            g = vals[vals.lead == h].dropna(subset=[f"{t}_obs"])
            r = float(np.sqrt(np.mean((g[t] - g[f"{t}_obs"]) ** 2)))
            print(f"{t} lead {h}: harness {r:.4f}  saved {saved[(t, h)]:.4f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("variants", nargs="*")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args()
    daily = load_daily()
    if a.check:
        check(daily)
    for n in a.variants:
        print(f"running {n}…", flush=True)
        run_variant(n, daily)
    if a.variants or a.compare:
        pd.set_option("display.width", 250)
        t = compare(list(VARIANTS))
        print(t.drop(columns=["thresholds"]).round(4).to_string(index=False))
