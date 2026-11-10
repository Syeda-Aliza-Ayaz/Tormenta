"""Every forecaster the backtest, the daily job and the apps run. Add new models here."""
from src.forecast.baselines import Climatology, Persistence, Recurrence27, TrailingMean


def baselines() -> list:
    return [Persistence(), Recurrence27(), TrailingMean(), Climatology()]


def all_models() -> list:
    return baselines()
