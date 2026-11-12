"""The GitHub workflow must be valid YAML: a parse error makes every run fail in 0 s, silently skipping retrains."""
import pytest

from src import config

yaml = pytest.importorskip("yaml")


def test_daily_workflow_parses_and_has_its_steps():
    wf = yaml.safe_load((config.ROOT / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8"))
    triggers = wf.get("on", wf.get(True))
    assert {"schedule", "workflow_dispatch"} <= set(triggers)
    crons = [c["cron"] for c in triggers["schedule"]]
    assert len(crons) >= 4                                  # GitHub delays schedules by hours (D-35)
    assert min(int(c.split()[1]) for c in crons) == 0       # first slot right after GFZ's ~23:45 UTC update
    names = [s.get("name") for s in wf["jobs"]["forecast"]["steps"]]
    for step in ["Issue, save NOAA, score", "Commit forecasts"]:
        assert step in names
    run = next(s["run"] for s in wf["jobs"]["forecast"]["steps"] if s.get("name") == "Commit forecasts")
    assert "git add forecasts" in run and "git pull --rebase" in run


def test_retrain_workflow_parses_and_has_its_steps():
    wf = yaml.safe_load((config.ROOT / ".github" / "workflows" / "retrain.yml").read_text(encoding="utf-8"))
    triggers = wf.get("on", wf.get(True))                   # YAML 1.1 reads the key `on` as boolean True
    assert {"schedule", "workflow_dispatch"} <= set(triggers)
    names = [s.get("name") for s in wf["jobs"]["retrain"]["steps"]]
    for step in ["Fetch, rebuild, retrain, gate", "Commit model and F10.7 history", "Publish to Hugging Face"]:
        assert step in names
