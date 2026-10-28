"""Metrics and report plots for Tormenta models."""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src import config


def metrics(y, pred) -> dict:
    """Overall RMSE/MAE/R² plus RMSE/MAE on storm hours (Kp ≥ 5-)."""
    y, pred = np.asarray(y), np.asarray(pred)
    storm = y >= config.STORM_THRESHOLD
    return {
        "rmse": mean_squared_error(y, pred) ** 0.5,
        "mae": mean_absolute_error(y, pred),
        "r2": r2_score(y, pred),
        "storm_rmse": mean_squared_error(y[storm], pred[storm]) ** 0.5 if storm.any() else np.nan,
        "storm_mae": mean_absolute_error(y[storm], pred[storm]) if storm.any() else np.nan,
        "n": len(y),
    }


def metrics_table(y, preds: dict) -> pd.DataFrame:
    return pd.DataFrame({name: metrics(y, p) for name, p in preds.items()}).T


def error_by_level(y, preds: dict) -> pd.DataFrame:
    """MAE and mean bias (pred − true) per storm level."""
    level = pd.cut(pd.Series(np.asarray(y)), bins=config.KP_BINS, labels=config.KP_BIN_LABELS, right=False)
    rows = {}
    for name, p in preds.items():
        err = pd.Series(np.asarray(p) - np.asarray(y))
        rows[(name, "MAE")] = err.abs().groupby(level, observed=False).mean()
        rows[(name, "bias")] = err.groupby(level, observed=False).mean()
    return pd.DataFrame(rows).T


def _save(fig, name):
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.FIGURES_DIR / f"{name}.png", bbox_inches="tight")


def plot_model_comparison(table: pd.DataFrame, title: str, name: str):
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    table["rmse"].plot.barh(ax=axes[0], color="#4C72B0")
    axes[0].set(title=f"{title}: RMSE (all hours)", xlabel="RMSE (Kp units)")
    table["storm_rmse"].plot.barh(ax=axes[1], color="#C44E52")
    axes[1].set(title=f"{title}: RMSE on storm hours (Kp ≥ 5-)", xlabel="RMSE (Kp units)")
    for ax in axes:
        ax.invert_yaxis()
    fig.tight_layout()
    _save(fig, name)
    return fig


def plot_overfitting(train_rmse: pd.Series, cv_rmse: pd.Series, val_rmse: pd.Series, name: str):
    df = pd.DataFrame({"train": train_rmse, "CV (train years)": cv_rmse, "validation": val_rmse})
    fig, ax = plt.subplots(figsize=(9, 4))
    df.plot.bar(ax=ax, rot=0)
    ax.set(title="Train vs CV vs validation RMSE (gap = overfitting)", ylabel="RMSE")
    _save(fig, name)
    return fig


def plot_pred_vs_actual(y, pred, title: str, name: str):
    y, pred = np.asarray(y), np.asarray(pred)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    hb = axes[0].hexbin(y, pred, gridsize=40, bins="log", cmap="viridis", extent=(0, 9, 0, 9))
    axes[0].plot([0, 9], [0, 9], "r--", lw=1)
    axes[0].set(title=f"{title}: predicted vs observed", xlabel="observed Kp", ylabel="predicted Kp")
    fig.colorbar(hb, ax=axes[0], label="hours (log)")
    resid = pred - y
    axes[1].hexbin(y, resid, gridsize=40, bins="log", cmap="magma")
    axes[1].axhline(0, color="w", lw=1)
    axes[1].set(title="Residual (pred − obs) vs observed", xlabel="observed Kp", ylabel="residual")
    fig.tight_layout()
    _save(fig, name)
    return fig


def plot_error_by_level(level_table: pd.DataFrame, name: str):
    mae = level_table.xs("MAE", level=1)
    bias = level_table.xs("bias", level=1)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4))
    mae.T.plot.bar(ax=axes[0], rot=0)
    axes[0].set(title="MAE by storm level (test)", xlabel="observed Kp level", ylabel="MAE")
    bias.T.plot.bar(ax=axes[1], rot=0, legend=False)
    axes[1].axhline(0, color="k", lw=1)
    axes[1].set(title="Mean bias (pred − obs) by level: negative = under-prediction", xlabel="observed Kp level")
    fig.tight_layout()
    _save(fig, name)
    return fig


def plot_permutation_importance(model, X, y, name: str, top: int = 20, n_rows: int = 20000):
    """Permutation importance on a strided sample (model-agnostic, works for HistGB)."""
    step = max(1, len(X) // n_rows)
    res = permutation_importance(model, X.iloc[::step], np.asarray(y)[::step], n_repeats=3,
                                 scoring="neg_root_mean_squared_error",
                                 random_state=config.RANDOM_STATE, n_jobs=1)
    imp = pd.Series(res.importances_mean, index=X.columns).sort_values().tail(top)
    fig, ax = plt.subplots(figsize=(8, 6))
    imp.plot.barh(ax=ax, color="#55A868")
    ax.set(title=f"Permutation importance (top {top}): RMSE increase when shuffled", xlabel="ΔRMSE")
    fig.tight_layout()
    _save(fig, name)
    return fig, imp.sort_values(ascending=False)


def plot_storm_case(y, pred, lo, hi, start: str, end: str, title: str, name: str):
    s = pd.DataFrame({"obs": y, "pred": pred, "lo": lo, "hi": hi}).loc[start:end]
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(s.index, s["lo"], s["hi"], alpha=0.25, label="80% interval")
    ax.plot(s.index, s["pred"], label="predicted")
    ax.step(s.index, s["obs"], where="post", color="crimson", label="observed (GFZ)")
    ax.axhline(config.STORM_THRESHOLD, color="grey", ls="--", lw=1)
    ax.set(title=title, ylabel="Kp", ylim=(0, 9.3))
    ax.legend(loc="upper left")
    _save(fig, name)
    return fig
