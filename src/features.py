"""Shared feature engineering — the ONLY place model features are defined.

Imported by training (src/train.py) and live serving (src/predict.py and the apps), so the
exact same transformation runs in both (no train/serve skew).

Inputs:
  hourly     — naive-UTC hourly frame with config.SW_FEATURES (gaps allowed)
  f107_daily — daily observed F10.7 series (GFZ in training; history file + SWPC live)

Every feature at hour t uses only data at or before t (tests/test_features.py checks this).
"""
import numpy as np
import pandas as pd

from src import config

PROTON_MASS_NPA = 1.6726e-6   # m_p · (cm⁻³ · (km/s)²) → nPa


def _min_periods(window: int) -> int:
    return max(2, window // 2)


def derived(sw: pd.DataFrame) -> pd.DataFrame:
    """Physics quantities recomputed from raw B/V/N/T — never taken from OMNI's columns."""
    V, N, T = sw["speed"], sw["density"], sw["temperature"]
    by, bz = sw["by_gsm"], sw["bz_gsm"]
    B = sw["b_scalar"].where(sw["b_scalar"] > 0)

    out = pd.DataFrame(index=sw.index)
    out["pressure"] = PROTON_MASS_NPA * N * V**2              # nPa, protons only (no alpha live)
    out["efield"] = -V * bz * 1e-3                            # mV/m
    out["vbs"] = V * (-bz).clip(lower=0) * 1e-3               # rectified E-field, mV/m
    out["beta"] = (4.16e-5 * T + 5.34) * N / B**2             # OMNI's definition
    out["mach_a"] = V * np.sqrt(N) / (20 * B)                 # OMNI's definition
    out["bt"] = np.hypot(by, bz)                              # transverse field
    out["sin_half_clock"] = np.abs(np.sin(np.arctan2(by, bz) / 2))
    out["newell"] = V ** (4 / 3) * out["bt"] ** (2 / 3) * out["sin_half_clock"] ** (8 / 3)
    return out


def history(base: pd.DataFrame) -> pd.DataFrame:
    """Lags and trailing rolling statistics (window ends at t, never centred)."""
    cols = {}
    for c in config.LAG_COLUMNS:
        for k in config.LAG_HOURS:
            cols[f"{c}_lag{k}h"] = base[c].shift(k)

    for w in config.ROLL_WINDOWS:
        for c in ["bz_gsm", "speed"]:
            roll = base[c].rolling(w, min_periods=_min_periods(w))
            cols[f"{c}_mean{w}h"] = roll.mean()
            cols[f"{c}_std{w}h"] = roll.std()
        cols[f"newell_mean{w}h"] = base["newell"].rolling(w, min_periods=_min_periods(w)).mean()

    cols["bz_min3h"] = base["bz_gsm"].rolling(3, min_periods=_min_periods(3)).min()
    cols["speed_max3h"] = base["speed"].rolling(3, min_periods=_min_periods(3)).max()
    for w in config.LONG_SPEED_WINDOWS:
        cols[f"speed_mean{w}h"] = base["speed"].rolling(w, min_periods=_min_periods(w)).mean()
    for w in config.LONG_NEWELL_WINDOWS:
        cols[f"newell_mean{w}h"] = base["newell"].rolling(w, min_periods=_min_periods(w)).mean()

    # Pressure dynamics: sudden compressions mark shock/CME arrival
    p = base["pressure"]
    cols["pressure_mean3h"] = p.rolling(3, min_periods=_min_periods(3)).mean()
    cols["pressure_max3h"] = p.rolling(3, min_periods=_min_periods(3)).max()
    cols["pressure_change1h"] = p - p.shift(1)
    return pd.DataFrame(cols, index=base.index)


def block_so_far(base: pd.DataFrame) -> pd.DataFrame:
    """Position inside the current 3-h Kp block and running stats since the block started.

    Uses only hours from the block start up to and including t (cumulative within the block),
    so it is causal; it tells the model how much of the block it has already seen.
    """
    block = base.index.floor(f"{config.KP_BLOCK_HOURS}h")
    cols = {"block_hour": base.index.hour % config.KP_BLOCK_HOURS}
    for c in config.BLOCK_SO_FAR_MEAN:
        s = base[c]
        n = s.notna().groupby(block).cumsum()
        cols[f"{c}_block_mean"] = s.fillna(0).groupby(block).cumsum() / n.where(n > 0)
    cols["newell_block_max"] = base["newell"].fillna(-np.inf).groupby(block).cummax().replace(-np.inf, np.nan)
    cols["bz_block_min"] = base["bz_gsm"].fillna(np.inf).groupby(block).cummin().replace(np.inf, np.nan)
    return pd.DataFrame(cols, index=base.index)


def storm_memory(base: pd.DataFrame) -> pd.DataFrame:
    """Exponentially decaying mean of energy input: a crude 'charge level' of the magnetosphere.

    Storms build up and recover over many hours, which fixed windows capture only coarsely.
    Weights 0.5^(k/half-life) for k = 0 … window-1 hours back, normalised over the hours that are
    present. The window is fixed (unlike pandas ewm over all history), so live serving with a
    few days of data computes exactly the same value as training. Needs ≥ half the weight present.
    """
    lags = np.arange(config.MEMORY_WINDOW_HOURS)
    cols = {}
    for c in config.MEMORY_COLUMNS:
        shifted = [base[c].shift(k) for k in lags]
        for hl in config.MEMORY_HALFLIVES:
            w = 0.5 ** (lags / hl)
            num = sum(wk * s.fillna(0) for wk, s in zip(w, shifted))
            den = sum(wk * s.notna() for wk, s in zip(w, shifted))
            cols[f"{c}_decay{hl}h"] = (num / den).where(den >= 0.5 * w.sum())
    return pd.DataFrame(cols, index=base.index)


def f107_daily_features(f107_daily: pd.Series) -> pd.DataFrame:
    """Daily F10.7 features usable on day D: previous day's value and trailing 81-day mean.

    The daily flux is measured ~20 UT, so day D's own value is not used. Flare-contaminated
    spikes (> 2× the trailing 27-day median of earlier days) are treated as missing.
    """
    s = f107_daily.sort_index().dropna()
    # Extend past the last measurement: live, today's flux is never known yet (measured ~20 UT), but today's
    # features only need earlier days. Without these rows the current day's hours would get NaN F10.7 features.
    days = pd.date_range(s.index.min(), s.index.max() + pd.Timedelta(days=config.F107_MAX_STALE_DAYS), freq="D")
    s = s.reindex(days)
    prior_median = s.shift(1).rolling(config.F107_SPIKE_WINDOW_DAYS, min_periods=10).median()
    clean = s.mask(s > config.F107_SPIKE_RATIO * prior_median)
    upto_yesterday = clean.shift(1)
    return pd.DataFrame({
        "f107_prev": upto_yesterday.ffill(limit=config.F107_MAX_STALE_DAYS),
        "f107_mean81d": upto_yesterday.rolling(config.F107_TRAILING_DAYS, min_periods=40).mean(),
    })


def time_features(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Cyclical hour-of-day and day-of-year (dipole tilt / season modulate coupling)."""
    hour = 2 * np.pi * index.hour / 24
    doy = 2 * np.pi * (index.day_of_year - 1) / 365.25
    return pd.DataFrame({"hour_sin": np.sin(hour), "hour_cos": np.cos(hour),
                         "doy_sin": np.sin(doy), "doy_cos": np.cos(doy)}, index=index)


def build_features(hourly: pd.DataFrame, f107_daily: pd.Series) -> pd.DataFrame:
    """Full feature matrix on a complete hourly grid (missing hours become NaN rows)."""
    sw = hourly[config.SW_FEATURES].sort_index().asfreq("h")
    base = pd.concat([sw, derived(sw)], axis=1)

    f107 = f107_daily_features(f107_daily).reindex(sw.index.normalize())
    f107.index = sw.index

    parts = [base, history(base), block_so_far(base)]
    if config.USE_MEMORY_FEATURES:
        parts.append(storm_memory(base))
    return pd.concat(parts + [f107, time_features(sw.index)], axis=1)


def monotonic_cst(columns) -> dict:
    """HistGB monotonic constraints for the columns present (+1 increasing, -1 decreasing)."""
    cst = {c: 1 for c in config.MONOTONIC_INCREASING}
    cst.update({c: -1 for c in config.MONOTONIC_DECREASING})
    return {c: v for c, v in cst.items() if c in set(columns)}


def kp_history_features(kp_hourly: pd.Series, index: pd.DatetimeIndex) -> pd.DataFrame:
    """ABLATION ONLY — never called by build_features, never used in production.

    Kp of the two previous *complete* blocks and the mean of the previous 8 blocks (24 h),
    relative to the block containing each hour. The current block's Kp is never used.
    Shows how much a model allowed to use past Kp (autoregression) would gain.
    """
    starts = kp_hourly[kp_hourly.index.hour % config.KP_BLOCK_HOURS == 0]
    kp_block = starts.asfreq(f"{config.KP_BLOCK_HOURS}h")
    block = index.floor(f"{config.KP_BLOCK_HOURS}h")
    prior = kp_block.shift(1)                       # value of the block before, stamped at this block
    out = pd.DataFrame({
        "kp_prev1": prior.reindex(block).to_numpy(),
        "kp_prev2": kp_block.shift(2).reindex(block).to_numpy(),
        "kp_prev_mean24h": prior.rolling(8, min_periods=4).mean().reindex(block).to_numpy(),
    }, index=index)
    return out
