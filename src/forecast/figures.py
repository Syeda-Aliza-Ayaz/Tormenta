"""Report figures for the forecaster (reports/forecast/figures/). Colours match the app (one fixed colour per model).

    python -m src.forecast.figures                 # every figure
    python -m src.forecast.figures --validation    # only the validation figures (05–07)
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


# ── Validation figures (2011–2019; the test period is not used) ───────────────────────────────────────────
EXP = config.FORECAST_REPORTS_DIR / "experiments"
VALIDATION_STYLE = {  # model: (label, colour, line style)
    "sw_rec_poisson": ("HistGB + solar wind (candidate)", "#0b4f9c", "-"), "baseline": ("HistGB (live model)", "#2a78d6", "-"),
    "gru": ("GRU", "#b04fc2", "-"), "lstm": ("LSTM", "#e87ba4", "-"), "holt_winters": ("Holt-Winters", "#eb6834", "--"),
}


def validation_models():
    """Skill per lead day for every model on the same 2011–2019 days (D-68 harness, D-75 comparison)."""
    from src.forecast import validate_yearly as V
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=False)
    for ax, target, title in zip(axes, config.FORECAST_TARGETS, ("Daily Ap", "Daily max Kp")):
        for m, (label, colour, ls) in VALIDATION_STYLE.items():
            path = V.OUT / m / "forecasts.csv"
            if not path.exists():
                continue
            sc = V.value_scores(pd.read_csv(path, parse_dates=["origin", "target_date"]))
            g = sc[sc.target == target].groupby("lead")[["sse", "sse_ref"]].sum()
            ax.plot(g.index, 1 - g.sse / g.sse_ref, ls, color=colour, lw=2.4 if m == "sw_rec_poisson" else 1.8,
                    marker="o", ms=3.5, label=label)
        ax.axhline(0, color=MUTED, lw=1)
        _style(ax, f"{title}: skill vs the 27-day average", "skill (0 = 27-day average)")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Validation 2011–2019 (same days for every model)", x=0.01, ha="left", fontsize=10, color=MUTED)
    fig.tight_layout()
    return fig


def validation_by_year():
    """Ap skill per year: live model, solar-wind candidate (D-68) and the locked model with coronal holes (D-70)."""
    t = pd.read_csv(EXP / "yearly" / "ap_skill_by_year.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(10, 4))
    x = t.index.to_numpy()
    bars = [("baseline", *VALIDATION_STYLE["baseline"][:2]), ("sw_rec_poisson", *VALIDATION_STYLE["sw_rec_poisson"][:2])]
    if "sw_rec_poisson_imagery" in t:
        bars.append(("sw_rec_poisson_imagery", "+ coronal holes (locked model; judged on 2013–2019)", "#eb6834"))
    w = 0.8 / len(bars)
    for i, (m, label, colour) in enumerate(bars):
        ax.bar(x + (i - (len(bars) - 1) / 2) * w, t[m], width=w, color=colour, label=label)
    ax.axhline(0, color=MUTED, lw=1)
    _style(ax, "Ap skill vs the 27-day average, year by year (validation 2011–2019)", "skill", leads=False)
    ax.set_xticks(x)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def noaa_storms():
    """Storm-warning skill (Heidke) vs NOAA's official forecast, 2017–2019 (D-71)."""
    t = pd.read_csv(EXP / "noaa_storm" / "summary.csv")
    fig, ax = plt.subplots(figsize=(8, 4))
    names = {"noaa": ("NOAA official", STYLE["noaa"][1]), "baseline": ("HistGB (live model)", "#2a78d6"),
             "sw_rec_poisson": ("HistGB + solar wind (candidate)", "#0b4f9c")}
    for off, (m, (label, colour)) in zip((-0.27, 0, 0.27), names.items()):
        g = t[t["forecaster"] == m].sort_values("lead")
        ax.bar(g["lead"] + off, g["heidke"], width=0.27, color=colour, label=label)
    _style(ax, "Storm warnings vs NOAA: Heidke skill (validation 2017–2019, 91 storm days)", "Heidke skill (0 = chance)")
    ax.set_xticks([1, 2, 3])
    ax.set_xlim(0.5, 3.5)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def coronal_hole_example(day="2016-11-20"):
    """One AIA 193 Å image with the detected coronal holes outlined, and the Earth-facing strip (D-70)."""
    import numpy as np
    from astropy.io import fits
    from scipy import ndimage
    from src.forecast import imagery
    path = imagery.IMAGES / f"AIA{pd.Timestamp(day):%Y%m%d}_0000_0193.fits"
    with fits.open(path) as h:
        hd, img = h[1].header, h[1].data.astype(float)
    img = img / hd["EXPTIME"]
    ny, nx = img.shape
    cx, cy, r = hd["CRPIX1"] - 1, hd["CRPIX2"] - 1, hd["RSUN_OBS"] / hd["CDELT1"]
    yy, xx = np.mgrid[0:ny, 0:nx]
    x, y = (xx - cx) / r, (yy - cy) / r
    disk = np.hypot(x, y) < 0.95
    dark = disk & (ndimage.median_filter(img, 5) < 0.35 * np.median(img[disk]))
    dark = ndimage.binary_opening(dark, structure=np.ones((7, 7)))
    lab, n = ndimage.label(dark)
    sizes = ndimage.sum(dark, lab, range(1, n + 1)) if n else np.array([])
    ch = np.isin(lab, 1 + np.flatnonzero(sizes >= 300))
    fig, axes = plt.subplots(1, 2, figsize=(10, 5.2))
    show = np.log10(np.clip(img, 1, None))
    for ax in axes:
        ax.imshow(show, cmap="gray", origin="lower", vmin=np.percentile(show[disk], 1), vmax=np.percentile(show[disk], 99.7))
        ax.set_xticks([]); ax.set_yticks([])
    axes[1].contour(ch, levels=[0.5], colors="#00c8ff", linewidths=1.2)
    for sx in (-0.3, 0.3):
        axes[1].axvline(cx + sx * r, color="#ffb000", lw=1, ls="--")
    axes[0].set_title(f"SDO/AIA 193 Å, {pd.Timestamp(day):%d %b %Y} 00:00 UTC", fontsize=10, loc="left")
    axes[1].set_title("Coronal holes (blue) and the Earth-facing strip (orange)", fontsize=10, loc="left")
    fig.tight_layout()
    return fig


def live_vs_archive():
    """Coronal-hole features from near-real-time vs archive images on the same 30 days (D-70 live check)."""
    t = pd.read_csv(EXP / "imagery" / "live_vs_archive.csv", parse_dates=["date"])
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8))
    for ax, (col, label) in zip(axes, [("ch_band_low", "Earth-facing, low latitude (%)"), ("ch_east", "incoming (%)"),
                                      ("ch_disk", "whole disk (%)")]):
        ax.scatter(t[f"{col}_arch"], t[f"{col}_nrt"], s=18, color="#2a78d6")
        lim = [0, max(t[f"{col}_arch"].max(), t[f"{col}_nrt"].max()) * 1.05]
        ax.plot(lim, lim, color=MUTED, lw=1)
        _style(ax, label, "near-real-time image", leads=False)
        ax.set_xlabel("archive image")
    fig.suptitle("Live vs archive images, 11 Oct – 9 Nov 2026 (30 days): every correlation 1.000", x=0.01, ha="left",
                 fontsize=10, color=MUTED)
    fig.tight_layout()
    return fig


def ch_vs_wind_lag():
    """Correlation of Earth-facing coronal-hole area with solar-wind speed and Ap 0–6 days later, 2011–2019."""
    import numpy as np
    from src.daily import load_daily
    from src.forecast import imagery
    from src.ingest import sw_archive
    ch = imagery.load()["ch_band_low"].loc["2011":"2019"]
    speed = sw_archive.omni_hourly()["speed"].resample("D").mean()
    ap = np.log1p(load_daily()["ap"])
    lags = range(0, 7)
    cs, ca = [], []
    for lag in lags:
        idx = ch.index + pd.Timedelta(days=lag)
        d = pd.DataFrame({"c": ch.to_numpy(), "s": speed.reindex(idx).to_numpy(), "a": ap.reindex(idx).to_numpy()}).dropna()
        cs.append(d["c"].corr(d["s"])); ca.append(d["c"].corr(d["a"]))
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.plot(list(lags), cs, "-o", color="#2a78d6", label="solar-wind speed")
    ax.plot(list(lags), ca, "-o", color="#eb6834", label="log Ap")
    ax.axhline(0, color=MUTED, lw=1)
    _style(ax, "Coronal-hole area today vs what arrives later (2011–2019)", "correlation", leads=False)
    ax.set_xlabel("days later"); ax.set_xticks(list(lags))
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def locked_test():
    """One-time test of the locked model, 2020-01 → 2026-06 (D-77): Ap error per lead day and storm Heidke."""
    d = config.FORECAST_REPORTS_DIR / "test_locked"
    leads, storms = pd.read_csv(d / "leads.csv"), pd.read_csv(d / "storms.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    ax = axes[0]
    ax.plot(leads["lead"], leads["ap_rmse_trailing27"], "--", color=MUTED, label="27-day average")
    ax.plot(leads["lead"], leads["ap_rmse_histgb"], "-o", color="#2a78d6", label="HistGB (live model)")
    n = leads.dropna(subset=["ap_rmse_noaa"])
    ax.plot(n["lead"], n["ap_rmse_noaa"], "-s", color=STYLE["noaa"][1], label="NOAA official")
    ax.plot(leads["lead"], leads["ap_rmse_locked"], "-o", color="#eb6834", label="locked model (+ solar wind, coronal holes)")
    _style(ax, "Daily Ap error (RMSE), lower is better", "Ap RMSE")
    ax.legend(frameon=False, fontsize=8)
    ax = axes[1]
    w = 0.38
    ax.bar(storms["lead"] - w / 2, storms["hss_histgb"], width=w, color="#2a78d6", label="HistGB (live model)")
    ax.bar(storms["lead"] + w / 2, storms["hss_locked"], width=w, color="#eb6834", label="locked model")
    _style(ax, "Storm warnings: Heidke skill (325 storm days)", "Heidke skill (0 = chance)")
    ax.legend(frameon=False, fontsize=8)
    fig.suptitle("One-time test, Jan 2020 – Jun 2026 (2,373 days), models fitted to 2019", x=0.01, ha="left",
                 fontsize=10, color=MUTED)
    fig.tight_layout()
    return fig


VALIDATION_FIGURES = [("05_validation_models", validation_models), ("06_validation_by_year", validation_by_year),
                      ("07_storms_vs_noaa", noaa_storms), ("08_coronal_hole_example", coronal_hole_example),
                      ("09_live_vs_archive_images", live_vs_archive), ("10_coronal_holes_vs_wind", ch_vs_wind_lag),
                      ("11_locked_test_vs_noaa", locked_test)]


def main():
    import sys
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    if "--validation" in sys.argv:                   # only the validation figures; the test figures stay as they are
        jobs = VALIDATION_FIGURES
    else:
        jobs = [("01_skill_vs_lead", skill_vs_lead), ("02_storm_skill_vs_lead", storm_skill),
                ("03_interval_coverage_test", coverage), ("04_may2024_case_study", case_study)] + VALIDATION_FIGURES
    for name, make in jobs:
        fig = make()
        fig.savefig(FIG_DIR / f"{name}.png", dpi=150)
        plt.close(fig)
        print(f"saved {name}.png")


if __name__ == "__main__":
    main()
