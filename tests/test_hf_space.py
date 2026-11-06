"""The Hugging Face uploads must contain everything the model code and landing page use."""
import importlib.util
import re

import pytest

from src import config

pytest.importorskip("huggingface_hub")


@pytest.fixture(scope="module")
def sync_hf():
    spec = importlib.util.spec_from_file_location("sync_hf", config.ROOT / "app" / "hf_space" / "sync_hf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_repo_is_complete(sync_hf):
    files = sync_hf.model_files()
    needed = {"README.md", "requirements.txt", "models/current.joblib", "data/f107_history.csv",
              "src/__init__.py", "src/config.py", "src/features.py", "src/predict.py", "src/evaluate.py",
              "src/ingest/__init__.py", "src/ingest/fetch_live.py"}
    assert needed <= set(files)
    assert all(path.exists() for path in files.values())


def test_space_page_images_are_uploaded(sync_hf):
    files = sync_hf.space_files()
    assert all(path.exists() for path in files.values())
    page = (config.ROOT / "app" / "hf_space" / "space" / "index.html").read_text(encoding="utf-8")
    assert set(re.findall(r'src="([^"]+)"', page)) <= set(files)
