"""Forecast scorecards (PLAN.md §7): error and skill per lead day, and storm-day detection.

Input everywhere: a long forecast frame with `model, origin, lead, target_date`, the predicted targets
(`ap`, `kpmax`) and the observed ones (`ap_obs`, `kpmax_obs`), as made by backtest.attach_actuals.
numpy/pandas only, so the browser app can import it.
"""
import numpy as np
import pandas as pd

from src import config

KEY = ["origin", "lead", "target_date"]


def lead_table(fc: pd.DataFrame,
               references=("persistence", "recurrence27", "trailing27", "climatology")) -> pd.DataFrame:
    """RMSE, MAE and skill score vs each reference, per model × target × lead day.

    Skill = 1 − MSE_model / MSE_reference on exactly the same forecasts (origin, lead) — > 0 beats the reference.
    """
    rows = []
    for target in config.FORECAST_TARGETS:
        obs = f"{target}_obs"
        scored = fc.dropna(subset=[target, obs])
        sq = scored.assign(se=(scored[target] - scored[obs]) ** 2, ae=(scored[target] - scored[obs]).abs())
        for (model, lead), g in sq.groupby(["model", "lead"]):
            row = {"model": model, "target": target, "lead": lead, "n": len(g),
                   "rmse": float(np.sqrt(g["se"].mean())), "mae": float(g["ae"].mean())}
            for ref in references:
                r = sq[(sq["model"] == ref) & (sq["lead"] == lead)][KEY + ["se"]]
                both = g[KEY + ["se"]].merge(r, on=KEY, suffixes=("", "_ref"))
                row[f"skill_vs_{ref}"] = (float(1 - both["se"].mean() / both["se_ref"].mean())
                                          if len(both) and both["se_ref"].mean() > 0 else np.nan)
            rows.append(row)
    return pd.DataFrame(rows)


def contingency(pred_yes, obs_yes) -> dict:
    """Hits/misses/false alarms → probability of detection, false alarm ratio, Heidke skill score."""
    pred_yes, obs_yes = np.asarray(pred_yes, bool), np.asarray(obs_yes, bool)
    a = int(np.sum(pred_yes & obs_yes))      # hits
    b = int(np.sum(pred_yes & ~obs_yes))     # false alarms
    c = int(np.sum(~pred_yes & obs_yes))     # misses
    d = int(np.sum(~pred_yes & ~obs_yes))    # correct negatives
    denom = (a + c) * (c + d) + (a + b) * (b + d)
    return {"hits": a, "false_alarms": b, "misses": c, "correct_negatives": d,
            "pod": a / (a + c) if a + c else np.nan,
            "far": b / (a + b) if a + b else np.nan,
            "hss": 2 * (a * d - b * c) / denom if denom else np.nan}


def storm_table(fc: pd.DataFrame, threshold: float = config.STORM_THRESHOLD) -> pd.DataFrame:
    """Storm day = max Kp ≥ 5− (G1+). A point forecast 'warns' when its predicted max Kp reaches it."""
    scored = fc.dropna(subset=["kpmax", "kpmax_obs"])
    rows = [{"model": model, "lead": lead, "n": len(g),
             **contingency(g["kpmax"] >= threshold, g["kpmax_obs"] >= threshold)}
            for (model, lead), g in scored.groupby(["model", "lead"])]
    return pd.DataFrame(rows)
