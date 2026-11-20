"""NOAA's storm-forecast skill on validation years, against ours on the same days (DECISIONS D-71).

NOAA's daily RSGA report gives, for the next three days, the chance of a minor storm and of a major-severe storm
at middle latitudes (section VI, "Geomagnetic Activity Probabilities"). NOAA's storm chance is their sum. Ours are
the storm probabilities from the yearly validation (D-68): `baseline` (the live model) and `sw_rec_poisson`.

Days: 2017–2019 (NOAA's archive starts in 2017; 2020 onward is the closed test period). Storm day: GFZ daily max
Kp >= 4.5. Scores per lead day 1–3: Brier score and its skill against the 2011–2016 storm rate; storm days caught,
false-alarm ratio and Heidke skill at each forecaster's own best threshold (same search for all, equally optimistic).

    python -m src.forecast.experiments.noaa_storm
"""
import ftplib
import re
import tarfile

import numpy as np
import pandas as pd

from src import config
from src.daily import load_daily
from src.ingest import fetch_noaa

YEARS = (2017, 2018, 2019)
RAW = config.RAW_DIR / "noaa_rsga_raw"
OUT = config.FORECAST_REPORTS_DIR / "experiments" / "noaa_storm"
YEARLY = config.FORECAST_REPORTS_DIR / "experiments" / "yearly"
OURS = ("baseline", "sw_rec_poisson")
GRID = np.round(np.arange(0.01, 0.91, 0.01), 2)

PROB_HEAD = re.compile(r"Geomagnetic Activity Probabilities\s+(\d{1,2} \w{3})-(\d{1,2} \w{3})", re.I)
MID_BLOCK = re.compile(r"Middle Latitudes(.*?)(?:B\.\s*High Latitudes|High Latitudes|\Z)", re.I | re.S)
MINOR = re.compile(r"Minor[ -]?storm\s+(\d+)/(\d+)/(\d+)", re.I)
MAJOR = re.compile(r"Major[ -]+severe[ -]?storm\s+(\d+)/(\d+)/(\d+)", re.I)


def download(year: int) -> "Path":  # noqa: F821
    """The year's RSGA tarball from the SWPC warehouse, kept as downloaded."""
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{year}_RSGA.tar.gz"
    if path.exists() and path.stat().st_size > 0:
        return path
    for attempt in range(1, 4):
        try:
            ftp = ftplib.FTP(fetch_noaa.FTP_HOST, timeout=3 * config.REQUEST_TIMEOUT)
            ftp.login()
            try:
                with open(path.with_suffix(".part"), "wb") as f:
                    ftp.retrbinary(f"RETR /pub/warehouse/{year}/{year}_RSGA.tar.gz", f.write)
            finally:
                try:
                    ftp.quit()
                except (OSError, ftplib.Error):
                    pass
            path.with_suffix(".part").replace(path)
            return path
        except (OSError, ftplib.Error) as exc:
            print(f"RSGA {year}: attempt {attempt} failed ({type(exc).__name__}: {exc})")
    raise RuntimeError(f"RSGA {year}: download failed")


def parse_storm_probs(text: str) -> pd.DataFrame:
    """Rows (issued, origin, lead, target_date, p_minor, p_major, p_storm) from one RSGA report; empty if absent."""
    issued = fetch_noaa._issued(text)
    head = PROB_HEAD.search(text)
    block = MID_BLOCK.search(text, head.end()) if head else None
    minor = MINOR.search(block.group(1)) if block else None
    major = MAJOR.search(block.group(1)) if block else None
    if not (head and minor and major):
        return pd.DataFrame()
    first = fetch_noaa._date_near(head.group(1), issued)
    p_minor = [int(x) / 100 for x in minor.groups()]
    p_major = [int(x) / 100 for x in major.groups()]
    rows = fetch_noaa._rows(issued, pd.date_range(first, periods=3, freq="D"), p_minor=p_minor, p_major=p_major)
    return rows.assign(p_storm=rows["p_minor"] + rows["p_major"])


def noaa_table() -> pd.DataFrame:
    frames, skipped = [], 0
    for year in YEARS:
        with tarfile.open(download(year), mode="r:gz") as tar:      # read in memory, never extracted to disk
            for m in tar.getmembers():
                if not (m.isfile() and m.name.endswith("RSGA.txt")):
                    continue
                text = tar.extractfile(m).read().decode("ascii", "replace")
                try:
                    df = parse_storm_probs(text)
                except ValueError:
                    df = pd.DataFrame()
                if len(df):
                    frames.append(df)
                else:
                    skipped += 1
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("issued").drop_duplicates(["origin", "lead"], keep="last")
    print(f"NOAA reports with storm probabilities: {out['origin'].nunique()} days ({skipped} reports without them)")
    return out


def _best_threshold(p, y):
    best = None
    for th in GRID:
        w = p >= th
        tp, fp = int((w & y).sum()), int((w & ~y).sum())
        fn, tn = int((~w & y).sum()), int((~w & ~y).sum())
        n = tp + fp + fn + tn
        expected = ((tp + fn) * (tp + fp) + (tn + fn) * (tn + fp)) / n
        hss = (tp + tn - expected) / (n - expected) if n != expected else 0.0
        if best is None or hss > best[0]:
            best = (hss, th, tp, fn, fp)
    return best


def compare() -> pd.DataFrame:
    noaa = noaa_table()
    daily = load_daily()
    clim = float((daily.loc["2011":"2016", "kpmax"] >= config.STORM_THRESHOLD).mean())
    ours = {name: pd.read_csv(YEARLY / name / "storm_probs.csv", parse_dates=["origin", "target_date"])
            for name in OURS}
    rows = []
    for lead in (1, 2, 3):
        merged = noaa[noaa["lead"] == lead][["origin", "target_date", "p_storm"]].rename(columns={"p_storm": "noaa"})
        for name, df in ours.items():
            merged = merged.merge(df[df["lead"] == lead][["origin", "storm_prob"]].rename(columns={"storm_prob": name}),
                                  on="origin")
        merged = merged[merged["target_date"].dt.year.isin(YEARS)]
        obs = daily["kpmax"].reindex(merged["target_date"]).to_numpy()
        keep = ~np.isnan(obs)
        merged, y = merged[keep], obs[keep] >= config.STORM_THRESHOLD
        ref = np.mean((clim - y) ** 2)
        for name in ("noaa", *OURS):
            p = merged[name].to_numpy()
            brier = float(np.mean((p - y) ** 2))
            hss, th, tp, fn, fp = _best_threshold(p, y)
            rows.append({"lead": lead, "forecaster": name, "days": len(y), "storm_days": int(y.sum()),
                         "brier": brier, "brier_skill": 1 - brier / ref, "best_threshold": th, "caught": tp,
                         "missed": fn, "false_alarms": fp, "detection": tp / max(tp + fn, 1),
                         "false_alarm_ratio": fp / max(tp + fp, 1), "heidke": hss})
    table = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "summary.csv", index=False)
    noaa.to_csv(OUT / "noaa_storm_probs_2017_2019.csv", index=False)
    return table


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    t = compare()
    print(t.round(3).to_string(index=False))
