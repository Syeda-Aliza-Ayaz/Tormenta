"""NOAA SWPC solar event reports and daily particle data (DECISIONS D-74).

  YYYY_events.tar.gz   one text file per day: X-ray flares (XRA), optical flares with position (FLA), radio
                       sweeps (RSP, type II/IV), radio bursts (RBR), with times and active region numbers
  YYYY_DPD.txt         daily proton fluence (>1, >10, >100 MeV)

From the FTP warehouse, kept as downloaded in data/raw/noaa_events/ (not committed). Only 1996–2019 is fetched for
the experiment; 2020 onward is the closed test period.

    python -m src.ingest.fetch_events            # download 1996–2019 (skips files already present)
"""
import ftplib
import time

from src import config

HOST = "ftp.swpc.noaa.gov"
RAW = config.RAW_DIR / "noaa_events"
YEARS = range(1996, 2020)


def _get(ftp: ftplib.FTP, remote: str, path) -> int:
    tmp = path.with_suffix(path.suffix + ".part")
    with open(tmp, "wb") as f:
        ftp.retrbinary(f"RETR {remote}", f.write)
    tmp.replace(path)
    return path.stat().st_size


def download(years=YEARS) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    jobs = [(y, f"/pub/warehouse/{y}/{y}_{kind}", RAW / f"{y}_{kind}")
            for y in years for kind in ("events.tar.gz", "DPD.txt")]
    todo = [j for j in jobs if not (j[2].exists() and j[2].stat().st_size > 0)]
    print(f"event reports: {len(jobs) - len(todo)} of {len(jobs)} files already here, {len(todo)} to fetch", flush=True)
    t0, done = time.time(), 0
    for year, remote, path in todo:
        for attempt in range(1, 4):
            try:
                ftp = ftplib.FTP(HOST, timeout=120)
                ftp.login()
                try:
                    size = _get(ftp, remote, path)
                finally:
                    try:
                        ftp.quit()
                    except (OSError, ftplib.Error):
                        pass
                break
            except (OSError, ftplib.Error) as exc:
                print(f"  {path.name}: attempt {attempt} failed ({type(exc).__name__}: {exc})", flush=True)
                size = None
        done += 1
        spent = time.time() - t0
        print(f"  [{done}/{len(todo)}] {path.name} {'%d kB' % (size // 1000) if size else 'FAILED'} | "
              f"elapsed {spent / 60:.1f} min | about {spent / done * (len(todo) - done) / 60:.0f} min left", flush=True)


if __name__ == "__main__":
    download()
