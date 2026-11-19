"""NASA DONKI coronal mass ejection (CME) catalogue → data/processed/cme_catalogue.csv (DECISIONS D-67).

Source: NASA CCMC Space Weather Database Of Notifications, Knowledge, Information (DONKI), through the api.nasa.gov
gateway (60 days per request). The API key is read from the NASA_API_KEY environment variable and is never stored.

Every CME keeps its submissionTime (when the entry appeared in the catalogue) and each arrival-model run keeps its
completion time, so a forecast can use only what was known when it was issued (DECISIONS D-67, option A).

    python -m src.ingest.fetch_donki                 # download 2010-01-01 → today, then build the table
    python -m src.ingest.fetch_donki --no-download   # rebuild the table from the saved responses
"""
import argparse
import json
import os
import time

import pandas as pd
import requests

from src import config

URL = "https://api.nasa.gov/DONKI/CME"
RAW_DIR = config.RAW_DIR / "donki_cme"
TABLE = config.PROCESSED_DIR / "cme_catalogue.csv"
START = pd.Timestamp("2010-01-01")
CHUNK_DAYS = 60


def _key() -> str:
    key = os.environ.get("NASA_API_KEY", "")
    if not key:
        raise SystemExit("Set NASA_API_KEY (free key from https://api.nasa.gov).")
    return key


def download(end: pd.Timestamp = None, refresh_days: int = 120) -> int:
    """Save one JSON file per 60-day window. Windows older than `refresh_days` are kept once saved, because
    entries and arrival-model runs keep being added for a while after an eruption."""
    end = (end or pd.Timestamp.now("UTC").tz_localize(None)).normalize()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    key, n = _key(), 0
    first = START
    while first <= end:
        last = min(first + pd.Timedelta(days=CHUNK_DAYS - 1), end)
        path = RAW_DIR / f"cme_{first:%Y%m%d}_{last:%Y%m%d}.json"
        fresh = (end - last).days < refresh_days
        if not path.exists() or fresh:
            for attempt in range(4):
                r = requests.get(URL, params={"startDate": f"{first:%Y-%m-%d}", "endDate": f"{last:%Y-%m-%d}",
                                              "api_key": key}, timeout=120)
                if r.status_code == 200:
                    break
                time.sleep(5 * (attempt + 1))
            r.raise_for_status()
            path.write_text(r.text or "[]", encoding="utf-8")
            n += 1
        first = last + pd.Timedelta(days=1)
    return n


def _utc(s):
    return pd.to_datetime(s, utc=True, errors="coerce").tz_localize(None) if s else pd.NaT


def build_table() -> pd.DataFrame:
    """One row per CME (its most accurate analysis) and its earliest Earth-arrival prediction."""
    rows = {}
    for path in sorted(RAW_DIR.glob("cme_*.json")):
        text = path.read_text(encoding="utf-8").strip()
        for e in json.loads(text) if text else []:
            analyses = e.get("cmeAnalyses") or []
            a = next((x for x in analyses if x.get("isMostAccurate")), analyses[0] if analyses else {})
            arrivals = []
            for x in analyses:
                for run in x.get("enlilList") or []:
                    t = _utc(run.get("estimatedShockArrivalTime"))
                    hit = run.get("isEarthGB") or t is not pd.NaT
                    if hit and t is not pd.NaT:
                        arrivals.append((_utc(run.get("modelCompletionTime")), t, run.get("kp_90"), run.get("kp_180")))
            arrivals = [x for x in arrivals if x[0] is not pd.NaT]
            first_pred = min(arrivals, default=None, key=lambda x: x[0])
            rows[e["activityID"]] = {
                "activity_id": e["activityID"], "start": _utc(e.get("startTime")),
                "submitted": _utc(e.get("submissionTime")),
                "analysis_submitted": _utc(a.get("submissionTime")),
                "speed": a.get("speed"), "half_angle": a.get("halfAngle"),
                "latitude": a.get("latitude"), "longitude": a.get("longitude"), "type": a.get("type"),
                "arrival_model_done": first_pred[0] if first_pred else pd.NaT,
                "predicted_arrival": first_pred[1] if first_pred else pd.NaT,
                "predicted_kp_90": first_pred[2] if first_pred else None,
            }
    table = pd.DataFrame(rows.values()).sort_values("start").reset_index(drop=True)
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(TABLE, index=False)
    return table


def load_table() -> pd.DataFrame:
    cols = ["start", "submitted", "analysis_submitted", "arrival_model_done", "predicted_arrival"]
    return pd.read_csv(TABLE, parse_dates=cols)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    if not ap.parse_args().no_download:
        print(f"downloaded {download()} windows")
    t = build_table()
    print(f"{len(t):,} CMEs {t['start'].min():%Y-%m-%d} -> {t['start'].max():%Y-%m-%d}; table {TABLE}")
