"""Report comparisons on the yearly harness: Holt-Winters, LSTM, GRU (DECISIONS D-75). Comparison only.

Forecasts the same rows as the D-68 harness (issue days through 2011–2019, lead days 1–7) and keeps the harness's
reference and observations, so the scores line up with `baseline` and `sw_rec_poisson`. Nothing live is used or
written.

    python -m src.forecast.experiments.report_models hw
    python -m src.forecast.experiments.report_models lstm gru
    python -m src.forecast.experiments.report_models --table
"""
import sys
import time

import numpy as np
import pandas as pd

from src import config
from src.daily import load_daily
from src.forecast import validate_yearly as V

YEARS = V.YEARS
LEADS = list(config.FORECAST_LEADS)
TARGETS = config.FORECAST_TARGETS                       # ["ap", "kpmax"]
SEASON = config.RECURRENCE_DAYS                         # 27 days, one solar rotation
HW_FIT_YEARS = 10
WINDOW = 81
SCALE = {"ap": 50.0, "kpmax": 9.0, "f107_obs": 200.0}   # fixed constants, nothing learned from the data


def harness_rows() -> pd.DataFrame:
    """Rows, reference and observations of the D-68 harness (from the live-model run)."""
    rows = pd.read_csv(V.OUT / "baseline" / "forecasts.csv", parse_dates=["origin", "target_date"])
    assert rows["target_date"].dt.year.max() < config.TEST_START_YEAR, "the test period is not used"
    return rows.drop(columns=TARGETS)


def history(daily: pd.DataFrame) -> pd.DataFrame:
    """Daily inputs, gaps filled from the past only (forward fill), so no value depends on later days."""
    return daily[["ap", "kpmax", "f107_obs"]].ffill()


# ── Holt-Winters: additive level + 27-day season ──────────────────────────────────────────────────────────────
def hw_run(y: np.ndarray, alpha: float, gamma: float, m: int = SEASON):
    """Level and seasonal states after each day. Initialised from the first two cycles."""
    n = len(y)
    level = np.empty(n)
    season = np.empty(n + m)
    l0 = y[:m].mean()
    season[:m] = y[:m] - l0
    lev = l0
    for t in range(n):
        s_old = season[t]
        new_lev = alpha * (y[t] - s_old) + (1 - alpha) * lev
        season[t + m] = gamma * (y[t] - new_lev) + (1 - gamma) * s_old
        lev = new_lev
        level[t] = lev
    return level, season


def hw_sse(params, y):
    alpha, gamma = params
    if not (0 < alpha < 1 and 0 < gamma < 1):
        return 1e18
    level, season = hw_run(y, alpha, gamma)
    pred = level[:-1] + season[1 + 0: len(y) - 1 + 1]         # one step ahead: l_t + s_{t+1-m}
    return float(np.sum((y[1:] - pred) ** 2))


def hw_fit(y: np.ndarray) -> tuple:
    from scipy.optimize import minimize
    best = None
    for a0, g0 in ((0.3, 0.1), (0.1, 0.05), (0.6, 0.2)):
        r = minimize(hw_sse, x0=[a0, g0], args=(y,), method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-3})
        if best is None or r.fun < best.fun:
            best = r
    return tuple(best.x)


def hw_forecasts(series: pd.Series, year: int, target: str) -> pd.DataFrame:
    """Forecasts for issue days D in [1 Jan - 7 d, 30 Dec] of `year`, each from data up to D only."""
    first = pd.Timestamp(f"{year}-01-01")
    fit_span = series.loc[first - pd.DateOffset(years=HW_FIT_YEARS): first - pd.Timedelta(days=1)]
    alpha, gamma = hw_fit(fit_span.to_numpy(float))
    run_span = series.loc[fit_span.index[0]: pd.Timestamp(f"{year}-12-30")]
    level, season = hw_run(run_span.to_numpy(float), alpha, gamma)
    idx = run_span.index
    origins = idx[idx >= first - pd.Timedelta(days=max(LEADS))]
    pos = idx.get_indexer(origins)
    out = []
    hi = 400.0 if target == "ap" else 9.0
    for h in LEADS:
        # season[t + m] is the state written on day t, so the season for day t + h is season[t + h]
        pred = np.clip(level[pos] + season[pos + h], 0, hi)
        out.append(pd.DataFrame({"origin": origins, "lead": h, target: pred}))
    return pd.concat(out, ignore_index=True)


def run_hw() -> pd.DataFrame:
    daily = load_daily()
    hist = history(daily)
    parts, t0 = [], time.time()
    for i, year in enumerate(YEARS, 1):
        ap = hw_forecasts(hist["ap"], year, "ap")
        kp = hw_forecasts(hist["kpmax"], year, "kpmax")
        parts.append(ap.merge(kp, on=["origin", "lead"]))
        spent = time.time() - t0
        print(f"  [{i}/{len(YEARS)}] holt_winters {year} done | elapsed {spent / 60:.1f} min | "
              f"about {spent / i * (len(YEARS) - i) / 60:.0f} min left", flush=True)
    return pd.concat(parts, ignore_index=True)


# ── LSTM / GRU ────────────────────────────────────────────────────────────────────────────────────────────────
def sequences(hist: pd.DataFrame, origins: pd.DatetimeIndex) -> np.ndarray:
    """(n, WINDOW, 5) inputs: Ap, max Kp, F10.7 (scaled) and the season (sin, cos), for the WINDOW days up to D."""
    x = pd.DataFrame({c: hist[c] / SCALE[c] for c in ("ap", "kpmax", "f107_obs")}, index=hist.index)
    doy = 2 * np.pi * hist.index.day_of_year / 365.25
    x["sin"], x["cos"] = np.sin(doy), np.cos(doy)
    arr = x.to_numpy(np.float32)
    pos = hist.index.get_indexer(origins)
    return np.stack([arr[p - WINDOW + 1: p + 1] for p in pos])


def targets(daily: pd.DataFrame, origins: pd.DatetimeIndex) -> np.ndarray:
    """(n, 14): Ap leads 1–7 then max Kp leads 1–7, scaled; NaN where a target is missing or not definitive."""
    cols = []
    for t in TARGETS:
        for h in LEADS:
            v = daily[t].where(daily["definitive"]).shift(-h).reindex(origins) / SCALE[t]
            cols.append(v.to_numpy(np.float32))
    return np.stack(cols, axis=1)


def train_rnn(cell: str, X: np.ndarray, Y: np.ndarray, Xv: np.ndarray, Yv: np.ndarray, seed: int = 7):
    import torch
    from torch import nn
    torch.manual_seed(seed)
    np.random.seed(seed)

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            rnn = nn.LSTM if cell == "lstm" else nn.GRU
            self.rnn = rnn(input_size=X.shape[2], hidden_size=64, batch_first=True)
            self.head = nn.Linear(64, Y.shape[1])

        def forward(self, x):
            out, _ = self.rnn(x)
            return self.head(out[:, -1])

    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    tX, tY = torch.from_numpy(X), torch.from_numpy(Y)
    vX, vY = torch.from_numpy(Xv), torch.from_numpy(Yv)

    def loss_fn(pred, y):
        ok = ~torch.isnan(y)
        return ((pred - torch.nan_to_num(y)) ** 2 * ok).sum() / ok.sum().clamp(min=1)

    best, best_state, bad = float("inf"), None, 0
    for epoch in range(30):
        net.train()
        perm = torch.randperm(len(tX))
        for b in range(0, len(perm), 256):
            i = perm[b: b + 256]
            opt.zero_grad()
            loss_fn(net(tX[i]), tY[i]).backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            v = float(loss_fn(net(vX), vY))
        if v < best - 1e-5:
            best, best_state, bad = v, {k: t.clone() for k, t in net.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 3:
                break
    net.load_state_dict(best_state)
    return net


def run_rnn(cell: str) -> pd.DataFrame:
    import torch
    daily = load_daily()
    hist = history(daily)
    start = pd.Timestamp(config.FORECAST_TRAIN_START) + pd.Timedelta(days=WINDOW)
    rows = harness_rows()
    parts, t0 = [], time.time()
    for i, year in enumerate(YEARS, 1):
        first = pd.Timestamp(f"{year}-01-01")
        last_origin = first - pd.Timedelta(days=max(LEADS) + 1)          # every target before 1 January
        train_o = hist.loc[start: last_origin].index
        cut = last_origin - pd.DateOffset(years=2)
        fit_o, val_o = train_o[train_o <= cut - pd.Timedelta(days=max(LEADS))], train_o[train_o > cut]
        X, Y = sequences(hist, fit_o), targets(daily, fit_o)
        Xv, Yv = sequences(hist, val_o), targets(daily, val_o)
        keep, keepv = ~np.isnan(X).any(axis=(1, 2)), ~np.isnan(Xv).any(axis=(1, 2))
        net = train_rnn(cell, X[keep], Y[keep], Xv[keepv], Yv[keepv])
        origins = pd.DatetimeIndex(sorted(rows.loc[rows["year"] == year, "origin"].unique()))
        with torch.no_grad():
            p = net(torch.from_numpy(sequences(hist, origins))).numpy()
        out = []
        for j, t in enumerate(TARGETS):
            for k, h in enumerate(LEADS):
                hi = 400.0 if t == "ap" else 9.0
                out.append(pd.DataFrame({"origin": origins, "lead": h, "target": t,
                                         "value": np.clip(p[:, j * len(LEADS) + k] * SCALE[t], 0, hi)}))
        df = pd.concat(out).pivot_table(index=["origin", "lead"], columns="target", values="value").reset_index()
        parts.append(df)
        spent = time.time() - t0
        print(f"  [{i}/{len(YEARS)}] {cell} {year} done | elapsed {spent / 60:.1f} min | "
              f"about {spent / i * (len(YEARS) - i) / 60:.0f} min left", flush=True)
    return pd.concat(parts, ignore_index=True)


# ── save and score like the harness ───────────────────────────────────────────────────────────────────────────
NAMES = {"hw": "holt_winters", "lstm": "lstm", "gru": "gru"}


def save(name: str, fc: pd.DataFrame) -> pd.DataFrame:
    rows = harness_rows().merge(fc, on=["origin", "lead"], how="left")
    assert rows[TARGETS].notna().all().all(), "every harness row needs a forecast"
    d = V.OUT / name
    d.mkdir(parents=True, exist_ok=True)
    rows.to_csv(d / "forecasts.csv", index=False)
    return rows


def table() -> pd.DataFrame:
    out = []
    for name in ("baseline", "sw_rec_poisson", "holt_winters", "lstm", "gru"):
        path = V.OUT / name / "forecasts.csv"
        if not path.exists():
            continue
        s = V.value_scores(pd.read_csv(path, parse_dates=["origin", "target_date"]))
        row = {"model": name}
        for t in TARGETS:
            g = s[s.target == t]
            pooled = g.groupby("lead")[["sse", "sse_ref", "sae", "n"]].sum()
            by_year = g.groupby(["year", "lead"])[["sse", "sse_ref"]].sum()
            yearly = (1 - by_year.sse / by_year.sse_ref).groupby("year").mean()
            row.update({f"{t}_skill": float((1 - pooled.sse / pooled.sse_ref).mean()),
                        f"{t}_rmse_d1": float(np.sqrt(pooled.sse[1] / pooled.n[1])),
                        f"{t}_rmse_d7": float(np.sqrt(pooled.sse[7] / pooled.n[7])),
                        f"{t}_years_above_ref": int((yearly > 0).sum())})
        out.append(row)
    t = pd.DataFrame(out)
    (V.OUT.parent / "report_models").mkdir(parents=True, exist_ok=True)
    t.to_csv(V.OUT.parent / "report_models" / "summary.csv", index=False)
    return t


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        if arg in NAMES:
            print(f"running {NAMES[arg]}", flush=True)
            save(NAMES[arg], run_hw() if arg == "hw" else run_rnn(arg))
    pd.set_option("display.width", 220)
    print(table().round(3).to_string(index=False))
