"""Figures for the final report, drawn at one-column width (8.6 cm) with 8-pt text so they stay readable in print.
Panels are stacked vertically. Output: docs/report/final/figs/.

    python -m src.report_figures           all figures (the first run refits the test-period nowcaster, ~4 min, and
                                           saves its May 2024 predictions to reports/metrics/may2024_test_nowcast.csv)
    python -m src.report_figures --quick   skip the May 2024 figure unless its predictions are already saved
"""
import argparse
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import config  # noqa: E402

OUT = config.ROOT / "docs" / "report" / "final" / "figs"
W = 3.4                                            # inches, one column of the two-column report
BLUE, ORANGE, GREY, RED, PURPLE = "#1f5fa8", "#e8692c", "#8a8a8a", "#c8102e", "#7b4fb0"
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "xtick.labelsize": 7,
                     "ytick.labelsize": 7, "legend.fontsize": 7, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6,
                     "savefig.dpi": 300, "font.family": "DejaVu Sans"})
T0 = time.time()


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"  saved {name}.png | {time.time() - T0:.0f} s", flush=True)


def hourly_training():
    from src.preprocessing import load_processed
    df = load_processed()
    df = df[df.index.year <= config.TRAIN_YEARS[1]]
    return df.assign(vbs=df["speed"] * (-df["bz_gsm"]).clip(lower=0) / 1000)


def eda(df):
    kp = df.loc[df["kp_definitive"], config.TARGET].dropna()

    # 1. distribution and class balance
    fig, ax = plt.subplots(figsize=(W, 1.7))
    ax.hist(kp, bins=np.arange(-1 / 6, 9.2, 1 / 3), color=BLUE)
    ax.set_yscale("log")
    ax.axvline(4.5, color=RED, ls="--", lw=1)
    share = (kp >= 4.5).mean()
    ax.text(4.6, ax.get_ylim()[1] * 0.35, f"storm (Kp ≥ 5−)\n{share:.1%} of hours", color=RED, fontsize=7)
    ax.set_xlabel("Kp"); ax.set_ylabel("hours (log scale)")
    ax.set_title("Kp distribution, training years 1998–2016", loc="left")
    save(fig, "eda1_kp_distribution")

    # 2. missing values
    cols = {"density": "density", "temperature": "temperature", "speed": "speed", "f107_obs": "F10.7",
            "bz_gsm": "Bz", "by_gsm": "By", "bx": "Bx", "b_scalar": "|B|"}
    miss = df[list(cols)].isna().mean().mul(100).rename(cols).sort_values()
    fig, ax = plt.subplots(figsize=(W, 1.6))
    ax.barh(miss.index, miss.values, color=ORANGE)
    for y, v in enumerate(miss.values):
        ax.text(v + 0.03, y, f"{v:.2f}%", va="center", fontsize=6.5)
    ax.set_xlabel("missing hours (%)"); ax.set_xlim(0, miss.max() * 1.25)
    ax.set_title("Missing values per input (gaps kept, not interpolated)", loc="left")
    save(fig, "eda2_missing")

    # 3. correlation with Kp
    names = {"speed": "speed", "temperature": "temperature", "b_scalar": "|B|", "vbs": "V·Bs", "f107_obs": "F10.7",
             "density": "density", "by_gsm": "By", "bx": "Bx", "bz_gsm": "Bz"}
    d = df.loc[df["kp_definitive"], [*names, config.TARGET]]
    rho = d.corr(method="spearman")[config.TARGET].drop(config.TARGET).rename(names).sort_values()
    fig, ax = plt.subplots(figsize=(W, 1.8))
    ax.barh(rho.index, rho.values, color=[RED if v < 0 else BLUE for v in rho.values])
    ax.axvline(0, color=GREY, lw=0.8)
    ax.set_xlabel("Spearman ρ with Kp")
    ax.set_title("Correlation with Kp (training years)", loc="left")
    save(fig, "eda3_correlation")

    # 4. Kp vs drivers, outliers kept: median and interquartile range per bin, stacked
    fig, axes = plt.subplots(2, 1, figsize=(W, 2.9))
    for ax, (col, bins, label) in zip(axes, [("bz_gsm", np.arange(-20, 21, 2.5), "Bz (nT)"),
                                             ("speed", np.arange(250, 901, 50), "speed (km/s)")]):
        g = d.groupby(pd.cut(d[col], bins), observed=True)[config.TARGET]
        mid = [i.mid for i in g.median().index]
        ax.fill_between(mid, g.quantile(0.25), g.quantile(0.75), color=BLUE, alpha=0.2, lw=0, label="25–75%")
        ax.plot(mid, g.median(), "-o", color=BLUE, ms=2.5, lw=1.2, label="median Kp")
        ax.axhline(4.5, color=RED, ls="--", lw=0.8)
        ax.set_xlabel(label); ax.set_ylabel("Kp")
        lo, hi = df[col].min(), df[col].max()
        ax.set_title(f"Kp vs {label.split(' ')[0]} (observed range {lo:.0f} to {hi:.0f})", loc="left")
    axes[0].legend(frameon=False, loc="upper right")
    fig.tight_layout(h_pad=0.6)
    save(fig, "eda4_kp_vs_drivers")

    # 5. daily Ap autocorrelation: the 27-day echo
    from src.daily import load_daily
    ap = np.log1p(load_daily()["ap"].loc["1947-06-01":"2016-12-31"])
    lags = np.arange(0, 121)
    acf = [ap.autocorr(int(k)) for k in lags]
    shuffled = pd.Series(np.random.default_rng(0).permutation(ap.to_numpy()))
    acf_s = [shuffled.autocorr(int(k)) for k in lags]
    fig, ax = plt.subplots(figsize=(W, 1.7))
    ax.plot(lags, acf, color=BLUE, lw=1, label="real order")
    ax.plot(lags, acf_s, color=ORANGE, lw=0.8, label="shuffled")
    for k in (27, 54, 81, 108):
        ax.axvline(k, color=GREY, ls=":", lw=0.8)
        ax.text(k + 1, 0.85, f"{k} d", fontsize=6.5, color=GREY)
    ax.set_xlabel("lag (days)"); ax.set_ylabel("autocorrelation"); ax.set_ylim(-0.05, 1)
    ax.set_title("Daily log Ap, 1947–2016: peaks every 27 days", loc="left")
    ax.legend(frameon=False, loc="center right")
    save(fig, "eda5_ap_autocorrelation")


def forecaster_test():
    d = config.FORECAST_REPORTS_DIR / "test_locked"
    leads, storms = pd.read_csv(d / "leads.csv"), pd.read_csv(d / "storms.csv")
    fig, axes = plt.subplots(2, 1, figsize=(W, 4.0))
    ax = axes[0]
    ax.plot(leads["lead"], leads["ap_rmse_trailing27"], "--", color=GREY, lw=1, label="27-day mean")
    ax.plot(leads["lead"], leads["ap_rmse_histgb"], "-o", color=BLUE, ms=3, lw=1.2, label="HistGB (indices only)")
    n = leads.dropna(subset=["ap_rmse_noaa"])
    ax.plot(n["lead"], n["ap_rmse_noaa"], "-s", color=PURPLE, ms=3, lw=1.2, label="NOAA official")
    ax.plot(leads["lead"], leads["ap_rmse_locked"], "-o", color=ORANGE, ms=3, lw=1.4, label="final (+SW, coronal holes)")
    ax.set_ylabel("Ap RMSE"); ax.set_xticks(range(1, 8)); ax.set_xlabel("lead day")
    ax.set_title("(a) Daily Ap error, lower is better", loc="left")
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.32), columnspacing=1.0)
    ax = axes[1]
    w = 0.38
    ax.bar(storms["lead"] - w / 2, storms["hss_histgb"], width=w, color=BLUE, label="HistGB (indices only)")
    ax.bar(storms["lead"] + w / 2, storms["hss_locked"], width=w, color=ORANGE, label="final model")
    ax.set_ylabel("Heidke skill"); ax.set_xticks(range(1, 8)); ax.set_xlabel("lead day")
    ax.set_title("(b) Storm warnings, 325 storm days", loc="left")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout(h_pad=0.8)
    save(fig, "res_forecaster_test")


MAY2024 = config.METRICS_DIR / "may2024_test_nowcast.csv"


def may2024_predictions():
    """The test-period nowcaster (fitted on 1998-2019, conformal margin), as in notebooks/03_modeling. Its hourly
    predictions for 9-14 May 2024 are saved once, so the figure can be redrawn without refitting."""
    if MAY2024.exists():
        return pd.read_csv(MAY2024, parse_dates=["time"], index_col="time")
    import joblib
    from src import train
    from src.predict import predict_with_interval
    X, y, _ = train.load_xy()
    params = {f"model__{k}": v for k, v in joblib.load(config.CURRENT_MODEL)["params"].items()}
    masks = train.split_masks(X.index)
    print("  conformal margin (out-of-fold, training and validation years) ...", flush=True)
    margin, _ = train.conformal_margin(params, X, y, masks, log=lambda *_: None)
    print(f"  margin {margin:+.3f}; fitting the 1998-2019 bundle ...", flush=True)
    case = train.fit_bundle(params, X, y, masks["train"] | masks["val"], margin=margin)
    band = predict_with_interval(case, X[masks["test"]])
    yt = y[masks["test"]]
    cover = ((yt >= band["kp_lo"]) & (yt <= band["kp_hi"])).mean()
    print(f"  test coverage {cover:.1%} (reported: 80.8%)", flush=True)
    out = band.loc["2024-05-09":"2024-05-14"].assign(kp_obs=yt.loc["2024-05-09":"2024-05-14"])
    out.index.name = "time"
    out.to_csv(MAY2024, float_format="%.4f")
    return out


def may2024():
    b = may2024_predictions()
    fig, ax = plt.subplots(figsize=(W, 2.2))
    ax.fill_between(b.index, b["kp_lo"], b["kp_hi"], color=BLUE, alpha=0.2, lw=0, label="80% interval")
    ax.plot(b.index, b["kp_pred"], color=BLUE, lw=1, label="nowcast")
    ax.step(b.index, b["kp_obs"], where="post", color=RED, lw=1, label="observed Kp (GFZ)")
    ax.axhline(4.5, color=GREY, ls="--", lw=0.8)
    ax.set_ylabel("Kp"); ax.set_ylim(0, 9.3)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    ax.set_title("May 2024 G5 storm (test year, never seen in training)", loc="left")
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.14), columnspacing=1.0)
    save(fig, "res_may2024")


def input_distributions(df):
    """Distributions of three solar-wind inputs, stacked (training years)."""
    fig, axes = plt.subplots(3, 1, figsize=(W, 3.9))
    for ax, (col, label, log) in zip(axes, [("speed", "speed (km/s)", False), ("bz_gsm", "Bz (nT)", False),
                                            ("density", "density (per cm3), log scale", True)]):
        v = df[col].dropna()
        if log:
            v = v[v > 0]
            ax.hist(v, bins=np.logspace(np.log10(v.min()), np.log10(v.max()), 60), color=BLUE)
            ax.set_xscale("log")
        else:
            ax.hist(v, bins=80, color=BLUE)
        ax.set_xlabel(label); ax.set_ylabel("hours")
        ax.set_title(f"{label.split(' (')[0]}: median {v.median():.1f}, range {v.min():.1f} to {v.max():.0f}", loc="left")
    fig.tight_layout(h_pad=0.4)
    save(fig, "eda6_input_distributions")


def model_comparison():
    """Nowcaster test RMSE per model, overall and on storm hours, stacked."""
    t = pd.read_csv(config.METRICS_DIR / "test.csv", index_col=0)
    t = t.drop(index=[i for i in t.index if i.startswith("Ensemble")])
    t.index = [i.replace(" (baseline)", "") for i in t.index]
    fig, axes = plt.subplots(2, 1, figsize=(W, 3.2))
    for ax, (col, title) in zip(axes, [("rmse", "(a) Test RMSE, all hours"),
                                       ("storm_rmse", "(b) Test RMSE, storm hours")]):
        v = t[col].sort_values(ascending=False)
        ax.barh(v.index, v.values, color=[ORANGE if i == "HistGB" else BLUE for i in v.index])
        for y, x in enumerate(v.values):
            ax.text(x + 0.01, y, f"{x:.3f}", va="center", fontsize=6.5)
        ax.set_xlim(0, v.max() * 1.15); ax.set_xlabel("RMSE (Kp)")
        ax.set_title(title, loc="left")
    fig.tight_layout(h_pad=0.6)
    save(fig, "res_model_comparison")


def fitting_curves():
    """Learning curve and complexity curve of the nowcaster, stacked."""
    lc = pd.read_csv(config.METRICS_DIR / "learning_curve.csv")
    cc = pd.read_csv(config.METRICS_DIR / "complexity_curve.csv")
    fig, axes = plt.subplots(2, 1, figsize=(W, 3.4))
    ax = axes[0]
    ax.plot(lc["training hours"], lc["train_rmse"], "-o", color=BLUE, ms=3, label="train")
    ax.plot(lc["training hours"], lc["val_rmse"], "-o", color=ORANGE, ms=3, label="validation")
    ax.set_xscale("log"); ax.set_xlabel("training hours (log scale)"); ax.set_ylabel("RMSE (Kp)")
    ax.set_title("(a) Learning curve: more data, the gap closes", loc="left")
    ax.legend(frameon=False)
    ax = axes[1]
    ax.plot(cc["max_leaf_nodes"], cc["train_rmse"], "-o", color=BLUE, ms=3, label="train")
    ax.plot(cc["max_leaf_nodes"], cc["val_rmse"], "-o", color=ORANGE, ms=3, label="validation")
    ax.axvline(31, color=GREY, ls=":", lw=0.8)
    ax.set_xscale("log", base=2); ax.set_xlabel("max leaf nodes per tree (31 chosen)"); ax.set_ylabel("RMSE (Kp)")
    ax.set_xticks(cc["max_leaf_nodes"]); ax.set_xticklabels(cc["max_leaf_nodes"])
    ax.set_title("(b) Complexity curve: validation flat, train keeps falling", loc="left")
    ax.legend(frameon=False)
    fig.tight_layout(h_pad=0.6)
    save(fig, "res_fitting_curves")


def error_by_level():
    """Test MAE and bias by observed storm level: persistence, Random Forest, HistGB, stacked."""
    t = pd.read_csv(config.METRICS_DIR / "test_error_by_level.csv", index_col=[0, 1])
    levels = list(t.columns)
    models = [("Persistence (baseline)", GREY, "persistence"), ("Random Forest", BLUE, "Random Forest"),
              ("HistGB", ORANGE, "HistGB")]
    fig, axes = plt.subplots(2, 1, figsize=(W, 3.4))
    x, w = np.arange(len(levels)), 0.26
    for ax, (metric, title) in zip(axes, [("MAE", "(a) Mean absolute error"),
                                          ("bias", "(b) Mean bias (negative = too low)")]):
        for k, (m, colour, label) in enumerate(models):
            ax.bar(x + (k - 1) * w, t.loc[(m, metric)].to_numpy(), width=w, color=colour, label=label)
        ax.set_xticks(x); ax.set_xticklabels(levels); ax.set_ylabel(f"{metric} (Kp)")
        ax.axhline(0, color=GREY, lw=0.8)
        ax.set_title(title, loc="left")
    axes[1].set_xlabel("observed Kp level")
    axes[0].set_ylim(0, 1.65)
    axes[0].legend(frameon=False, ncol=3, loc="upper left")
    fig.tight_layout(h_pad=0.6)
    save(fig, "res_error_by_level")


def storm_confusion():
    """Confusion matrices of the final storm classifier on the test period, lead days 1 and 3, stacked."""
    d = config.FORECAST_REPORTS_DIR / "test_locked"
    probs = pd.read_csv(d / "storm_probs.csv.gz")
    probs = probs[probs["obs_definitive"]]
    th = pd.read_csv(d / "storms.csv").set_index("lead")["threshold"]
    fig, axes = plt.subplots(2, 1, figsize=(W, 3.6))
    for ax, h in zip(axes, (1, 3)):
        g = probs[probs["lead"] == h]
        warn, obs = g["storm_prob"] >= th[h], g["storm_obs"].astype(bool)
        m = np.array([[(~warn & ~obs).sum(), (warn & ~obs).sum()], [(~warn & obs).sum(), (warn & obs).sum()]])
        ax.imshow(m, cmap="Blues", vmin=0, vmax=m.max() * 1.6)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f"{m[i, j]:,}", ha="center", va="center", fontsize=9)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["no warning", "warning"])
        ax.set_yticks([0, 1]); ax.set_yticklabels(["no storm", "storm"])
        ax.grid(False)
        pod, far = m[1, 1] / m[1].sum(), m[0, 1] / m[:, 1].sum()
        ax.set_title(f"Lead day {h}: detects {pod:.0%} of storms, {far:.0%} false alarms", loc="left")
    fig.tight_layout(h_pad=0.8)
    save(fig, "res_storm_confusion")


def coronal_hole_example(day="2016-11-20"):
    """One AIA 193 A image and its detected coronal holes with the Earth-facing strip, stacked."""
    from astropy.io import fits
    from scipy import ndimage
    from src.forecast import imagery
    with fits.open(imagery.IMAGES / f"AIA{pd.Timestamp(day):%Y%m%d}_0000_0193.fits") as h:
        hd, img = h[1].header, h[1].data.astype(float)
    img = img / hd["EXPTIME"]
    ny, nx = img.shape
    cx, cy, r = hd["CRPIX1"] - 1, hd["CRPIX2"] - 1, hd["RSUN_OBS"] / hd["CDELT1"]
    yy, xx = np.mgrid[0:ny, 0:nx]
    disk = np.hypot((xx - cx) / r, (yy - cy) / r) < 0.95
    dark = disk & (ndimage.median_filter(img, 5) < 0.35 * np.median(img[disk]))
    dark = ndimage.binary_opening(dark, structure=np.ones((7, 7)))
    lab, n = ndimage.label(dark)
    sizes = ndimage.sum(dark, lab, range(1, n + 1)) if n else np.array([])
    ch = np.isin(lab, 1 + np.flatnonzero(sizes >= 300))
    show = np.log10(np.clip(img, 1, None))
    lo, hi = np.percentile(show[disk], 1), np.percentile(show[disk], 99.7)
    fig, axes = plt.subplots(2, 1, figsize=(W * 0.72, 5.0))
    for ax in axes:
        ax.imshow(show, cmap="gray", origin="lower", vmin=lo, vmax=hi)
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for side in ("top", "right", "left", "bottom"):
            ax.spines[side].set_visible(False)
    axes[1].contour(ch, levels=[0.5], colors="#00c8ff", linewidths=0.8)
    for sx in (-0.3, 0.3):
        axes[1].axvline(cx + sx * r, color="#ffb000", lw=0.8, ls="--")
    axes[0].set_title(f"(a) SDO/AIA 193 Å, {pd.Timestamp(day):%d %b %Y}", loc="left")
    axes[1].set_title("(b) coronal holes (blue), Earth-facing strip (orange)", loc="left")
    fig.tight_layout(h_pad=0.5)
    save(fig, "res_coronal_hole")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--quick", action="store_true", help="skip the May 2024 refit")
    a = p.parse_args()
    print("[1/3] EDA figures", flush=True)
    df = hourly_training()
    eda(df)
    input_distributions(df)
    print("[2/3] results figures", flush=True)
    forecaster_test()
    model_comparison()
    fitting_curves()
    error_by_level()
    storm_confusion()
    coronal_hole_example()
    if not a.quick or MAY2024.exists():
        print("[3/3] May 2024 nowcast (refits on 1998-2019 only if its saved predictions are missing)", flush=True)
        may2024()


if __name__ == "__main__":
    main()
