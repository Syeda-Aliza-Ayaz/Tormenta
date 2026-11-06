"""Weekly retrain guard rails (no network: data refresh is stubbed)."""
import pytest

from src import config, update

pytestmark = pytest.mark.skipif(not (config.PROCESSED_CSV.exists() and config.CURRENT_MODEL.exists()),
                                reason="needs the local processed table and current model")


def test_no_new_data_means_no_retrain(monkeypatch):
    """With the same data the current model was trained on, the holdout has not moved: do nothing."""
    monkeypatch.setattr(update, "refresh_data", lambda write_f107=True: None)
    monkeypatch.setattr(update.train, "fit_production", lambda *a, **k: pytest.fail("must not retrain"))
    assert update.run(dry_run=True) == {"status": "no_new_data", "promoted": False}


def test_github_output(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    update._github_output({"status": "promoted", "promoted": True, "version": "tormenta_vX"})
    assert out.read_text() == "status=promoted\npromoted=true\nversion=tormenta_vX\n"
