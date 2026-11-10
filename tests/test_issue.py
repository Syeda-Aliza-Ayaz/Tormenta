"""Daily job guards: issue only from yesterday's data, never change or backfill the log, score the right days."""
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src import config, issue
from src.forecast import registry


@pytest.fixture
def gfz():
    """Synthetic GFZ daily frame: definitive until 2026-06-30, then provisional, then nowcast; ends 2026-11-09."""
    rng = np.random.default_rng(2)
    days = pd.date_range("2015-01-01", "2026-11-09", freq="D", name="date")
    kp = rng.choice(np.arange(0, 9.01, 1 / 3), size=(len(days), 8))
    df = pd.DataFrame(kp, index=days, columns=[f"kp{i}" for i in range(1, 9)])
    df["ap_daily"] = rng.integers(0, 60, len(days)).astype(float)
    df["f107_obs"] = 120.0
    df["gfz_flag"] = np.where(days <= "2026-06-30", 2, np.where(days <= "2026-11-01", 1, 0))
    df["definitive"] = df["gfz_flag"] == 2
    return df


@pytest.fixture
def paths(tmp_path, monkeypatch):
    for name, rel in [("FORECASTS_DIR", ""), ("FORECAST_LOG", "log.csv"), ("FORECAST_SCORES", "scores.csv"),
                      ("FORECAST_RECENT", "recent.csv"), ("NOAA_LIVE_CSV", "noaa_live.csv"), ("NOAA_LIVE_DIR", "noaa")]:
        monkeypatch.setattr(config, name, tmp_path / rel)
    return tmp_path


@pytest.fixture
def offline(gfz, paths, monkeypatch):
    monkeypatch.setattr(issue, "load_gfz_daily", lambda: gfz)
    monkeypatch.setattr(issue, "production_window", lambda daily: daily.loc[:"2019-12-31"])  # keep the test fast
    return gfz


def _run(day: str):
    return issue.run(download=False, now=pd.Timestamp(day))


def test_choose_origin_needs_yesterday(gfz):
    from src.daily import build_daily
    daily = build_daily(gfz)
    assert issue.choose_origin(daily, pd.Timestamp("2026-11-10")) == pd.Timestamp("2026-11-09")
    assert issue.choose_origin(daily, pd.Timestamp("2026-11-12")) is None          # GFZ two days behind
    partial = gfz.copy()
    partial.loc[pd.Timestamp("2026-11-10")] = partial.iloc[-1]
    partial.loc[pd.Timestamp("2026-11-10"), "kp8"] = np.nan                           # today, still incomplete
    assert issue.choose_origin(build_daily(partial), pd.Timestamp("2026-11-10")) == pd.Timestamp("2026-11-09")


def test_issue_writes_every_model_and_lead(offline, paths):
    out = _run("2026-11-10 02:05")
    log = out["log"]
    assert out["origin"] == pd.Timestamp("2026-11-09") and out["new_rows"] == len(log)
    assert len(log) == len(registry.production_models()) * len(config.FORECAST_LEADS)
    assert list(log.columns) == issue.LOG_COLUMNS
    assert (log["origin_flag"] == 0).all() and (log["issued_at"] == pd.Timestamp("2026-11-10 02:05")).all()
    for f in ["log.csv", "scores.csv", "recent.csv", "noaa_live.csv"]:
        assert (paths / f).exists(), f


def test_log_is_append_only_and_idempotent(offline, paths):
    _run("2026-11-10 02:05")
    first = pd.read_csv(paths / "log.csv")
    again = _run("2026-11-10 06:00")                         # backup run, same day
    assert again["new_rows"] == 0
    pd.testing.assert_frame_equal(pd.read_csv(paths / "log.csv"), first)


def test_new_day_adds_rows_and_keeps_old_ones_unchanged(offline, gfz, paths, monkeypatch):
    _run("2026-11-10 02:05")
    first = pd.read_csv(paths / "log.csv")
    nxt = gfz.copy()
    nxt.loc[pd.Timestamp("2026-11-10")] = nxt.iloc[-1]
    monkeypatch.setattr(issue, "load_gfz_daily", lambda: nxt)
    _run("2026-11-11 02:05")
    log = pd.read_csv(paths / "log.csv")
    pd.testing.assert_frame_equal(log.iloc[:len(first)], first)
    assert set(log.iloc[len(first):]["origin"]) == {"2026-11-10"}


def test_late_gfz_issues_nothing_and_never_backfills(offline, paths):
    out = _run("2026-11-12 02:05")                          # GFZ still ends 2026-11-09
    assert out["origin"] is None and out["new_rows"] == 0
    assert len(pd.read_csv(paths / "log.csv")) == 0


def test_scores_pair_each_forecast_with_its_target_day(offline, gfz, paths, monkeypatch):
    _run("2026-11-10 02:05")
    later = gfz.copy()
    for d in pd.date_range("2026-11-10", "2026-11-12"):
        later.loc[d] = later.iloc[-1]
        later.loc[d, "ap_daily"] = 100.0 + d.day           # recognisable observed values
    monkeypatch.setattr(issue, "load_gfz_daily", lambda: later)
    scores = _run("2026-11-13 02:05")["scores"]
    first_issue = scores[scores["origin"] == pd.Timestamp("2026-11-09")]
    assert sorted(first_issue["lead"].unique()) == [1, 2, 3]  # only the target days that have arrived
    assert (first_issue["ap_obs"] == 100.0 + first_issue["target_date"].dt.day).all()
    assert np.allclose(first_issue["ap_err"], first_issue["ap"] - first_issue["ap_obs"])


def test_noaa_failure_is_a_warning_and_duplicates_are_dropped(paths, capsys):
    texts = {config.NOAA_27DO: (config.ROOT / "tests" / "data" / "noaa_27do_20261109.txt").read_text()}

    def fake_fetch(url):
        if url in texts:
            return texts[url]
        raise ConnectionError("down")

    out = issue.save_noaa(fake_fetch)
    out.to_csv(config.NOAA_LIVE_CSV, index=False)
    assert "NOAA 3day not saved" in capsys.readouterr().out
    assert len(out) == 27 and (paths / "noaa" / "27do" / "20261109_0258.txt").exists()
    assert len(issue.save_noaa(fake_fetch)) == 27           # same outlook fetched again: no duplicates


def test_committed_log_rows_are_unchanged():
    """Local guard: every row of forecasts/log.csv in the last commit must still be in the working copy, as is."""
    git = shutil.which("git")
    if not git or not config.FORECAST_LOG.exists():
        pytest.skip("no git or no log yet")
    head = subprocess.run([git, "show", "HEAD:forecasts/log.csv"], cwd=config.ROOT, capture_output=True, text=True)
    if head.returncode != 0:
        pytest.skip("log not committed yet")
    committed = head.stdout.splitlines()
    current = config.FORECAST_LOG.read_text(encoding="utf-8").splitlines()
    assert current[:len(committed)] == committed, "forecasts/log.csv: committed rows were changed or removed"
