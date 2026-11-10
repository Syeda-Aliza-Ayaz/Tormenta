"""Every forecaster the backtest, the daily job and the apps run. Add new models here."""
from src.forecast.baselines import Climatology, Persistence, Recurrence27, TrailingMean
from src.forecast import gbm
from src.forecast.gbm import HistGBDirect, load_params


def baselines() -> list:
    return [Persistence(), Recurrence27(), TrailingMean(), Climatology()]


def trained() -> list:
    """Unfitted trained models with their tuned settings (backtests fit them on the period's training rows)."""
    params, log_ap = load_params()
    return [HistGBDirect(params, log_ap=log_ap)]


def all_models() -> list:
    return baselines() + trained()


def production_models() -> list:
    """Models the daily job issues with.

    Baselines are refitted each run on the fixed production window (train + validation, src/issue.py). Trained
    models are loaded from their saved bundle and never refitted here (DECISIONS D-12, D-27). A bundle exists only
    if the model passed its validation rule (DECISIONS D-31), so an unsaved model is simply not issued.
    """
    models = baselines()
    if gbm.BUNDLE.exists():
        models.append(HistGBDirect.load())
    return models
