"""The GitHub workflow must be valid YAML: a parse error makes every run fail in 0 s, silently skipping retrains."""
import pytest

from src import config

yaml = pytest.importorskip("yaml")


def test_retrain_workflow_parses_and_has_its_steps():
    wf = yaml.safe_load((config.ROOT / ".github" / "workflows" / "retrain.yml").read_text(encoding="utf-8"))
    triggers = wf.get("on", wf.get(True))                   # YAML 1.1 reads the key `on` as boolean True
    assert {"schedule", "workflow_dispatch"} <= set(triggers)
    names = [s.get("name") for s in wf["jobs"]["retrain"]["steps"]]
    for step in ["Fetch, rebuild, retrain, gate", "Commit model and F10.7 history", "Publish to Hugging Face"]:
        assert step in names
