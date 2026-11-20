"""Hourly nowcast log (ROADMAP 5a): keep every hour's live Kp estimate so its accuracy can be scored later.

The site computes the nowcast on demand and keeps no record. The daily job calls `update()`, which runs the nowcast
on NOAA's live solar-wind feed (7 days of data) and appends each completed hour to

  forecasts/nowcast_log.csv   time (UTC hour), kp_pred, kp_lo, kp_hi, model_trained_until, logged_at

Rules:
  - Append-only: an hour already in the log keeps its first value; later runs only add new hours.
  - Completed hours only: the hour in progress and the "next hour" forecast are not stored.
  - The feed holds 7 days, so a late or missed run loses nothing as long as one run happens within 7 days.
  - A failure only prints a warning; it never blocks the forecast.
"""
import pandas as pd

from src import config

COLUMNS = ["kp_pred", "kp_lo", "kp_hi", "model_trained_until", "logged_at"]


def load(path=None) -> pd.DataFrame:
    path = path or config.NOWCAST_LOG
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], name="time"))
    return pd.read_csv(path, parse_dates=["time", "logged_at"], index_col="time")


def merge(log: pd.DataFrame, pred: pd.DataFrame, now: pd.Timestamp, trained_until: str) -> pd.DataFrame:
    """Add completed hours from `pred` (predict_hourly output) that the log does not have yet."""
    done = pred[(pred.index < now.floor("h")) & ~pred.get("ahead", pd.Series(False, index=pred.index)).astype(bool)]
    new = done.loc[~done.index.isin(log.index), ["kp_pred", "kp_lo", "kp_hi"]].copy()
    if new.empty:
        return log
    new["model_trained_until"] = trained_until
    new["logged_at"] = now.floor("s")
    out = pd.concat([log, new]) if len(log) else new
    out.index.name = "time"
    return out.sort_index()


def update(run=None, now: pd.Timestamp = None, path=None) -> pd.DataFrame:
    """Run the live nowcast and append its completed hours. Returns the log (unchanged on failure)."""
    path = path or config.NOWCAST_LOG
    now = now or pd.Timestamp.now(tz="UTC").tz_localize(None)
    log = load(path)
    try:
        if run is None:
            from src.predict import load_bundle, nowcast
            bundle = load_bundle()
            pred, _ = nowcast(bundle, now)
            trained_until = str(bundle.get("trained_until", ""))
        else:
            pred, trained_until = run()
    except Exception as exc:                      # noqa: BLE001 - the log must never block the forecast
        print(f"WARNING: nowcast not logged ({type(exc).__name__}: {exc})")
        return log
    out = merge(log, pred, now, trained_until)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, float_format="%.4g", date_format="%Y-%m-%d %H:%M:%S")
    print(f"nowcast log: {len(out)} hours ({len(out) - len(log):+d} this run), last {out.index.max()}")
    return out


if __name__ == "__main__":
    update()
