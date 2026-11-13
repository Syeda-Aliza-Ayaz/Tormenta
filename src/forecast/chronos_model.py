"""Chronos-Bolt, a pretrained time-series transformer, used zero-shot (PLAN.md §6, DECISIONS D-11).

Pretrained by Amazon with self-supervised learning on many time series; we do NOT train it. For each issue day D it
receives the last CONTEXT_DAYS daily values up to D (never later) and returns D+1 … D+7. Ap and max Kp are
forecast as two separate series. It sees no F10.7, season or other features: only the series itself.

Optional dependency (torch + chronos-forecasting): when they are missing, `available()` is False and the registry
leaves the model out, so the rest of the project runs without them.

    python -m src.forecast.chronos_model    # validation + recent hindcast, the rule, and the live marker file
"""
import json

import numpy as np
import pandas as pd

from src import config
from src.forecast.base import Forecaster, as_origins, stack

MODEL_ID = "amazon/chronos-bolt-small"
CONTEXT_DAYS = 512           # ~19 solar rotations of history per forecast
BATCH = 256
MARKER = config.MODELS_DIR / "forecast" / "chronos.json"     # exists only if Chronos passed its rule
TARGET_MAX = {"ap": 400.0, "kpmax": 9.0}


def available() -> bool:
    try:
        import chronos  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


class ChronosForecaster(Forecaster):
    name = "chronos"

    def __init__(self, model_id: str = MODEL_ID, context_days: int = CONTEXT_DAYS):
        self.model_id, self.context_days = model_id, context_days
        self.version = model_id.split("/")[-1]
        self.frozen = True               # pretrained: nothing to fit
        self._pipeline = None

    def fit(self, daily):
        return self

    def pipeline(self):
        if self._pipeline is None:
            import torch
            from chronos import BaseChronosPipeline
            self._pipeline = BaseChronosPipeline.from_pretrained(self.model_id, device_map="cpu",
                                                                 torch_dtype=torch.float32)
        return self._pipeline

    def _forecast(self, series: pd.Series, origins: pd.DatetimeIndex) -> np.ndarray:
        """(len(origins), 7) median forecasts; each context ends at its origin."""
        import torch
        values = series.to_numpy(dtype=float)
        pos = series.index.get_indexer(origins)
        out = []
        for start in range(0, len(pos), BATCH):
            ctx = [torch.tensor(values[max(0, p - self.context_days + 1): p + 1]) for p in pos[start:start + BATCH]]
            quantiles, _ = self.pipeline().predict_quantiles(ctx, prediction_length=len(config.FORECAST_LEADS),
                                                             quantile_levels=[0.5])
            out.append(quantiles[..., 0].numpy())
        return np.concatenate(out)

    def predict(self, daily, origins):
        origins = as_origins(daily, origins)
        per_lead = {h: {} for h in config.FORECAST_LEADS}
        for t in config.FORECAST_TARGETS:
            series = daily[t].loc[: origins.max()]          # NaN gaps are allowed: Chronos treats them as missing
            pred = np.clip(self._forecast(series, origins), 0, TARGET_MAX[t])
            for i, h in enumerate(config.FORECAST_LEADS):
                per_lead[h][t] = pred[:, i]
        return stack(origins, per_lead)

    def __getstate__(self):                                  # never pickle the loaded network
        return {**self.__dict__, "_pipeline": None}


def live() -> bool:
    return MARKER.exists() and available()


def main() -> dict:
    from src import backtest, scorecard
    from src.daily import load_daily
    from src.forecast.baselines import TrailingMean

    daily = load_daily()
    model = ChronosForecaster()
    out = config.FORECAST_REPORTS_DIR / "metrics"
    results = {}
    for name in ("validation", "recent"):
        first, last = backtest.period(name, daily)
        origins = backtest.origins_for(first, last)
        fc = model.predict(daily, origins).assign(model=model.name)
        fc = backtest.attach_actuals(fc[fc["target_date"].between(first, last)], daily)
        fc = fc[fc["obs_definitive"]] if name == "validation" else fc.dropna(subset=["ap_obs"])
        fc.to_csv(config.FORECAST_REPORTS_DIR / f"chronos_{name}_forecasts.csv.gz", index=False)
        results[name] = fc
        print(f"{name}: {fc['origin'].nunique()} issue days")

    # the same rule as every trained model (D-31): mean Ap skill vs trailing27 on validation > 0
    val = results["validation"]
    ref = backtest.run([TrailingMean()], daily, *backtest.period("validation", daily))
    leads = scorecard.lead_table(pd.concat([val, ref], ignore_index=True), references=("trailing27",))
    skill = float(leads[(leads["model"] == "chronos") & (leads["target"] == "ap")]["skill_vs_trailing27"].mean())
    passed = skill > 0
    leads.to_csv(out / "chronos_validation_leads.csv", index=False)
    print(f"chronos: mean Ap skill vs trailing27 = {skill:+.3f} -> {'PASS' if passed else 'FAIL'}")
    if passed:
        MARKER.write_text(json.dumps({"model_id": model.model_id, "context_days": model.context_days,
                                      "validation_skill_vs_trailing27": skill}, indent=2), encoding="utf-8")
    elif MARKER.exists():
        MARKER.unlink()
    return {"skill": skill, "passed": passed, "leads": leads, **results}


if __name__ == "__main__":
    main()
