"""The Hugging Face Space upload must contain everything app.py imports or loads."""
import importlib.util

import pytest

from src import config

pytest.importorskip("huggingface_hub")


def test_space_upload_is_complete():
    spec = importlib.util.spec_from_file_location("sync_hf", config.ROOT / "app" / "hf_space" / "sync_hf.py")
    sync_hf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync_hf)
    files = sync_hf.files_to_upload()
    needed = {"app.py", "README.md", "requirements.txt", "models/current.joblib", "data/f107_history.csv",
              "src/__init__.py", "src/config.py", "src/features.py", "src/predict.py", "src/evaluate.py",
              "src/ingest/__init__.py", "src/ingest/fetch_live.py"}
    assert needed <= set(files)
    assert all(path.exists() for path in files.values())
