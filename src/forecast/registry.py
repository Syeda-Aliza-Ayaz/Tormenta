"""Every forecaster the backtest, the daily job and the apps run. Add new models here."""
from src.forecast.baselines import Climatology, Persistence, Recurrence27, TrailingMean


def baselines() -> list:
    return [Persistence(), Recurrence27(), TrailingMean(), Climatology()]


def all_models() -> list:
    return baselines()


def production_models() -> list:
    """Models the daily job issues with. Baselines are refitted each run on the fixed production window
    (train + validation, src/issue.py); trained models will be loaded from saved bundles instead, and refitted only
    by the retrain path when the monitor says so (DECISIONS D-12)."""
    return all_models()
