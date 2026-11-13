"""Report figures for the forecaster (reports/forecast/figures/). Colours match the app (one fixed colour per model).

    python -m src.forecast.figures
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src import config  # noqa: E402

FIG_DIR = config.FORECAST_REPORTS_DIR / "figures"
METRICS = config.FORECAST_REPORTS_DIR / "metrics"
STYLE = {  # model: (label, colour, line style)
    "histgb": ("HistGB", "#2a78d6", "-"), "arima": ("ARIMA", "#eb6834", "-"),
    "sarima": ("SARIMA (27-day)", "#1baf7a", "-"), "arimax": ("ARIMAX", "#eda100", "-"),
    "noaa": ("NOAA official", "#e87ba4", "-"), "trailing27": ("27-day average", "#008300", "--"),
    "persistence": ("persistence", "#6250d6", ":"), "recurrence27": ("recurrence", "#e34948", ":"),
    "chronos": ("Chronos (transformer)", "#5a5955", "-."), "storm_warning": ("Storm warning (classifier)", "#2a78d6", "-"),
}
INK, MUTED = "#3d3d3a", "#8a8985"


def _style(ax, title, ylabel, leads=True):
    ax.set_title(title, fontsize=11, loc="left", color=INK)
    ax.set_ylabel(ylabel)
    if leads:                                         # lead-day axis; date axes keep their own ticks
        ax.set_xlabel("lead day")
        ax.set_xticks(config.FORECAST_LEADS)
    ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _lines(ax, table, value, models):
    for m in models:
        g = table[table["model"] == m].sort_values("lead")
        if len(g):
            label, colour, ls = STYLE[m]
            ax.plot(g["lead"], g[value], ls, color=colour, lw=2, marker="o", ms=4, label=label)


def skill_vs_lead(periods=("validation", "test")):
    fig, axes = plt.subplots(1, len(periods), figsize=(6 * len(periods), 4), sharey=True)
    for ax, period in zip(axes, periods):
        t = pd.read_csv(METRICS / f"{period}_leads.csv")
        chronos = METRICS / "chronos_validation_leads.csv"
        if period == "validation" and "chronos" not in set(t["model"]) and chronos.exists():
            t = pd.concat([t, pd.read_csv(chronos)])
        t = t[t["target"] == "ap"]
        ax.axhline(0, color=MUTED, lw=1)
        _lines(ax, t, "skill_vs_trailing27", ["histgb", "noaa", "arimax", "arima", "chronos", "sarima", "persistence"])
        _style(ax, f"{period.capitalize()}: Ap skill vs the 27-day average", "skill (1 − MSE / MSE of 27-day average)")
    axes[0].set_ylim(-0.6, 0.45)
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, loc="lower center", ncol=len(labels))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    return fig


def storm_skill(periods=("validation", "test")):
    fig, axes = plt.subplots(1, len(periods), figsize=(6 * len(periods), 4), sharey=True)
    for ax, period in zip(axes, periods):
        t = pd.concat([pd.read_csv(METRICS / f"{period}_storms.csv"),
                       pd.read_csv(METRICS / f"{period}_storm_warning.csv")])
        ax.axhline(0, color=MUTED, lw=1)
        _lines(ax, t, "hss", ["storm_warning", "recurrence27", "persistence", "arimax"])
        histgb = t[t["model"] == "histgb"].sort_values("lead")
        ax.plot(histgb["lead"], histgb["hss"], "--", color=STYLE["histgb"][1], lw=1.5, marker="o", ms=3,
                label="HistGB (value forecast)")
        _style(ax, f"{period.capitalize()}: storm-day Heidke skill", "Heidke skill score")
    axes[-1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def coverage(period="test"):
    t = pd.read_csv(METRICS / f"{period}_interval_coverage.csv")
    t = t[t["target"] == "ap"]
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.axhline(0.8, color=MUTED, lw=1, ls="--")
    ax.text(1, 0.803, "80% target", va="bottom", color=MUTED, fontsize=8)
    _lines(ax, t, "coverage", ["histgb", "arimax", "trailing27", "persistence", "recurrence27"])
    _style(ax, f"{period.capitalize()}: share of days inside the 80% Ap range", "coverage")
    ax.set_ylim(0.6, 0.95)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout()
    return fig


def case_study(start="2024-04-25", end="2024-05-25"):
    """What each model forecast for the May 2024 superstorm, 1 and 3 days ahead, with the storm risk."""
    fc = pd.read_csv(config.FORECAST_REPORTS_DIR / "test_forecasts.csv.gz", parse_dates=["origin", "target_date"])
    warn = pd.read_csv(config.FORECAST_REPORTS_DIR / "test_storm_warning_forecasts.csv.gz",
                       parse_dates=["origin", "target_date"])
    from src.daily import load_daily
    obs = load_daily().loc[start:end, "ap"]
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True, gridspec_kw={"height_ratios": [3, 3, 2]})
    for ax, lead in zip(axes[:2], (1, 3)):
        ax.plot(obs.index, obs, color=INK, lw=2, marker="o", ms=3, label="observed Ap (GFZ)")
        for m in ("histgb", "noaa", "arimax", "trailing27"):
            g = fc[(fc["model"] == m) & (fc["lead"] == lead) & fc["target_date"].between(start, end)]
            if len(g):
                label, colour, ls = STYLE[m]
                ax.plot(g["target_date"], g["ap"], ls, color=colour, lw=1.8, label=label)
        ax.set_yscale("symlog", linthresh=30)
        _style(ax, f"Forecast issued {lead} day{'s' if lead > 1 else ''} ahead", "Ap (log scale above 30)",
               leads=False)
    axes[0].legend(frameon=False, fontsize=8, ncol=3)
    for lead, ls in ((1, "-"), (3, "--")):
        g = warn[(warn["lead"] == lead) & warn["target_date"].between(start, end)]
        axes[2].plot(g["target_date"], g["storm_prob"], ls, color=STYLE["storm_warning"][1], lw=1.8,
                     label=f"storm risk, {lead} day{'s' if lead > 1 else ''} ahead")
    storm_days = obs.index[load_daily().loc[start:end, "kpmax"] >= config.STORM_THRESHOLD]
    for d in storm_days:
        axes[2].axvspan(d - pd.Timedelta(hours=12), d + pd.Timedelta(hours=12), color="#d03b3b", alpha=0.12, lw=0)
    _style(axes[2], "Storm risk (shaded: observed storm days)", "P(storm)", leads=False)
    axes[2].set_ylim(0, 1)
    axes[2].legend(frameon=False, fontsize=8)
    axes[2].set_xticks(pd.date_range(start, end, freq="5D"))
    axes[2].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    fig.tight_layout()
    return fig


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for name, make in [("01_skill_vs_lead", skill_vs_lead), ("02_storm_skill_vs_lead", storm_skill),
                       ("03_interval_coverage_test", coverage), ("04_may2024_case_study", case_study)]:
        fig = make()
        fig.savefig(FIG_DIR / f"{name}.png", dpi=150)
        plt.close(fig)
        print(f"saved {name}.png")


if __name__ == "__main__":
    main()
