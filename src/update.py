"""Slow loop: fetch fresh data → rebuild the hourly table → retrain the frozen configuration → gate → promote.

Run weekly by .github/workflows/retrain.yml, or by hand:
    python -m src.update              # full run: may write models/ and data/f107_history.csv
    python -m src.update --dry-run    # everything up to the gate decision, writes nothing tracked by git

What is retrained: the FROZEN final configuration (same 66 features, same HistGB settings, same conformal
margin as models/current.joblib). Nothing is re-tuned and the 2020+ test set is not re-scored: the new model
is trained on those years, so its only fair check is the gate holdout (last 6 months of definitive Kp).

Leakage safeguards (from the plan):
  - the processed table is rebuilt from scratch each run (never committed);
  - the candidate is trained only up to the start of the holdout;
  - candidate and current model are both scored on the same holdout, in this run, and
    gate_decision asserts the current model never saw it.
"""
import argparse
import os
from datetime import datetime, timezone

import pandas as pd

from src import config, train
from src.ingest.fetch_gfz import download_gfz, load_gfz_daily
from src.ingest.fetch_omni import load_omni_spdf
from src.predict import load_bundle
from src.preprocessing import build_f107_history, build_hourly, check, save_processed

FIRST_YEAR = 1998


def refresh_data(write_f107: bool = True):
    """Download GFZ + every SPDF yearly OMNI file and rebuild data/processed/ from scratch."""
    download_gfz()
    gfz = load_gfz_daily()
    omni = load_omni_spdf(FIRST_YEAR, datetime.now(timezone.utc).year)
    df = build_hourly(omni, gfz)
    check(df)
    save_processed(df)
    if write_f107:
        build_f107_history(gfz)
    print(f"OMNI {omni.index.min()} → {omni.index.max()} | hourly table ends {df.index.max()}")
    return df


def nowcaster_health(incumbent: dict, X, y, persistence) -> dict:
    """Skill vs persistence (1 − MSE / MSE of the previous Kp block) on the gate holdout, compared with the
    test-period skill of the same model type (reports/metrics/test.csv)."""
    import numpy as np
    test = pd.read_csv(config.METRICS_DIR / "test.csv", index_col=0)
    reference = 1 - (test.loc["HistGB", "rmse"] / test.loc["Persistence (baseline)", "rmse"]) ** 2
    hold = train._holdout_mask(y)
    rmse = train.gate_metrics(incumbent, X, y)["rmse"]
    rmse_persist = float(np.sqrt(np.mean((persistence[hold] - y[hold]) ** 2)))
    skill = 1 - (rmse / rmse_persist) ** 2
    floor = reference - config.NOWCAST_HEALTH_MARGIN
    return {"skill": float(skill), "reference": float(reference), "floor": float(floor),
            "status": "healthy" if skill >= floor else "degraded"}


def run(dry_run: bool = False) -> dict:
    refresh_data(write_f107=not dry_run)
    X, y, persistence = train.load_xy()
    incumbent = load_bundle()
    assert list(X.columns) == incumbent["features"], "feature set changed: retrain needs a new tuning round"

    hold_start = y.index[train._holdout_mask(y)].min()
    print(f"definitive labels with features end {y.index.max()} | gate holdout starts {hold_start}")
    print(f"current model {incumbent['version']} trained until {incumbent['trained_until']}")
    # The candidate would train on hours before hold_start; if that adds nothing, retraining is pointless
    if hold_start <= pd.Timestamp(incumbent["trained_until"]) + pd.Timedelta("1h"):
        print("No new definitive data since the current model was trained → nothing to do.")
        return {"status": "no_new_data", "promoted": False}

    # Retrain only when the current model performs badly (DECISIONS D-53): its skill vs persistence on the newest
    # 6 months must stay within HEALTH_MARGIN of its test-period skill, otherwise nothing is retrained.
    health = nowcaster_health(incumbent, X, y, persistence)
    print(f"current model on the holdout: skill vs persistence {health['skill']:.3f} "
          f"(test {health['reference']:.3f}, floor {health['floor']:.3f}) → {health['status']}")
    if health["status"] == "healthy":
        return {**{f"health_{k}": v for k, v in health.items()}, "status": "healthy_no_retrain", "promoted": False}

    params = {f"model__{k}": v for k, v in incumbent["params"].items()}
    margin = incumbent.get("interval_margin", 0.0)
    candidate, gate = train.fit_production(params, X, y, margin=margin)
    promote, incumbent_gate = train.gate_decision(gate, X, y)
    print(f"candidate gate RMSE {gate['rmse']:.4f} vs current {incumbent_gate['rmse']:.4f} "
          f"(tolerance ×{config.GATE_TOLERANCE}) → promote: {promote}")

    result = {"status": "promoted" if promote else "rejected", "promoted": promote,
              "candidate_rmse": gate["rmse"], "current_rmse": incumbent_gate["rmse"]}
    if dry_run:
        print("Dry run: nothing saved.")
        return {**result, "status": f"dry_run_{result['status']}", "promoted": False}

    result["version"] = train.save_bundle(candidate, {}, gate, promote, incumbent_gate, keep_rejected=False,
                                          note="weekly retrain (frozen configuration; test set not re-scored)")
    print(f"logged {result['version']} in metrics_history.json (promoted={promote})")
    return result


def _github_output(result: dict) -> None:
    """Expose the outcome to later workflow steps (no-op outside GitHub Actions)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"status={result['status']}\npromoted={str(result['promoted']).lower()}\n"
                     f"version={result.get('version', '')}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="stop after the gate decision; save nothing")
    _github_output(run(ap.parse_args().dry_run))
