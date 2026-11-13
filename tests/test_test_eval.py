"""The test period is scored once: a second run must refuse without --force."""
import pytest

from src.forecast import test_eval


def test_second_run_refuses_without_force(tmp_path, monkeypatch):
    marker = tmp_path / "test_scored.json"
    marker.write_text("{}")
    monkeypatch.setattr(test_eval, "MARKER", marker)
    with pytest.raises(SystemExit, match="already scored"):
        test_eval.main()
