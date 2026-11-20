"""Daily warning-sign inputs from NOAA's event reports and particle data (DECISIONS D-74).

For issue day D, events that began on D or the two days before (all known when the forecast is issued):
  ev_xray_max         log10 peak X-ray flux of the largest flare (W/m²; no flare → -8, the A1 floor)
  ev_xray_central     the same, only flares from regions whose optical flare position was within 30° of disk centre
  ev_type2            number of type II radio sweeps
  ev_type4            number of type IV radio sweeps
  ev_proton10         log10 of the largest daily >10 MeV proton fluence
"""
import re
import tarfile

import numpy as np
import pandas as pd

from src.ingest.fetch_events import RAW

FLOOR = -8.0                                                  # A1.0 flare, 1e-8 W/m²
SCALE = {"A": 1e-8, "B": 1e-7, "C": 1e-6, "M": 1e-5, "X": 1e-4}
LINE = re.compile(r"^\s*(\d{4,5})\s+\+?\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)$")
POS = re.compile(r"^([NS])(\d{1,2})([EW])(\d{1,2})$")
DATE = re.compile(r"^:Date:\s+(\d{4})\s+(\d{1,2})\s+(\d{1,2})", re.M)
DATE_OLD = re.compile(r"EDITED EVENTS for (\d{4}) (\w{3}) (\d{1,2})", re.I)       # 1990s layout
WINDOW_DAYS = 3


def xray_flux(cls: str) -> float:
    m = re.match(r"^([ABCMX])(\d+(?:\.\d+)?)$", cls.strip())
    return SCALE[m.group(1)] * float(m.group(2)) if m else np.nan


def parse_day(text: str) -> dict:
    """One day's report → raw daily values (before the 3-day window)."""
    d = DATE.search(text)
    if d:
        day = pd.Timestamp(int(d.group(1)), int(d.group(2)), int(d.group(3)))
    else:
        d = DATE_OLD.search(text)
        if not d:
            raise ValueError("no date line")
        day = pd.to_datetime(f"{d.group(1)} {d.group(2)} {d.group(3)}", format="%Y %b %d")
    xra, central_regions, type2, type4 = [], set(), 0, 0
    for line in text.splitlines():
        if not line or line.startswith((":", "#")):
            continue
        m = LINE.match(line)
        if not m:
            continue
        kind, loc, rest = m.group(7), m.group(8), m.group(9)
        tokens = rest.split()
        region = tokens[-1] if tokens and re.fullmatch(r"\d{4,5}", tokens[-1]) else None
        if kind == "XRA" and tokens:
            xra.append((xray_flux(tokens[0]), region))
        elif kind == "FLA":
            p = POS.match(loc)
            if p and region and int(p.group(2)) <= 30 and int(p.group(4)) <= 30:
                central_regions.add(region)
        elif kind == "RSP" and tokens:
            sweep = tokens[0].split("/")[0]
            type2 += sweep == "II"
            type4 += sweep == "IV"
    flux = [f for f, _ in xra if f == f]
    central = [f for f, r in xra if f == f and r in central_regions]
    return {"date": day, "xray_max": max(flux) if flux else np.nan, "xray_central": max(central) if central else np.nan,
            "type2": type2, "type4": type4, "n_reports": 1}


def daily_events(years) -> pd.DataFrame:
    rows = []
    for year in years:
        path = RAW / f"{year}_events.tar.gz"
        if not path.exists():
            continue
        with tarfile.open(path, mode="r:gz") as tar:              # read in memory, never extracted to disk
            for m in tar.getmembers():
                if m.isfile() and m.name.endswith("events.txt"):
                    try:
                        rows.append(parse_day(tar.extractfile(m).read().decode("ascii", "replace")))
                    except ValueError:
                        pass
    return pd.DataFrame(rows).groupby("date").max() if rows else pd.DataFrame()


def daily_protons(years) -> pd.Series:
    vals = {}
    for year in years:
        path = RAW / f"{year}_DPD.txt"
        if not path.exists():
            continue
        for line in path.read_text(encoding="ascii", errors="replace").splitlines():
            parts = line.split()
            if len(parts) < 6 or line.startswith(("#", ":")):
                continue
            try:
                if re.fullmatch(r"\d{1,2}", parts[0]) and re.fullmatch(r"[A-Za-z]{3}", parts[1]):    # 01 Jan 96
                    day = pd.to_datetime(f"{parts[0]} {parts[1]} {parts[2]}", format="%d %b %y")
                elif re.fullmatch(r"\d{4}", parts[0]):                                              # 2010 01 01
                    day = pd.Timestamp(int(parts[0]), int(parts[1]), int(parts[2]))
                else:
                    continue
                vals[day] = float(parts[4])                        # >10 MeV fluence in both layouts
            except ValueError:
                continue
    s = pd.Series(vals, dtype=float).sort_index()
    return s.where(s > 0)


def event_features(index: pd.DatetimeIndex, years=range(1996, 2020)) -> pd.DataFrame:
    """Inputs per issue day D over D-2 … D. Days without a report stay blank (not zero)."""
    ev = daily_events(years).reindex(index)
    pr = daily_protons(years).reindex(index)
    have = ev["n_reports"].notna().rolling(WINDOW_DAYS, min_periods=1).sum() > 0
    w = lambda s, how: getattr(s.rolling(WINDOW_DAYS, min_periods=1), how)()  # noqa: E731
    out = pd.DataFrame(index=index)
    out["ev_xray_max"] = np.log10(w(ev["xray_max"], "max")).fillna(FLOOR).where(have)
    out["ev_xray_central"] = np.log10(w(ev["xray_central"], "max")).fillna(FLOOR).where(have)
    out["ev_type2"] = w(ev["type2"].fillna(0), "sum").where(have)
    out["ev_type4"] = w(ev["type4"].fillna(0), "sum").where(have)
    out["ev_proton10"] = np.log10(w(pr, "max"))
    return out
