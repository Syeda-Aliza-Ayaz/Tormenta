"""The Hugging Face uploads must contain everything the model code and the in-browser Space use."""
import ast
import importlib.util
import json
import re
import warnings

import pytest
import sklearn

from src import config
from src.portable import save_portable
from src.predict import load_bundle

pytest.importorskip("huggingface_hub")

HEAVY = {"sklearn", "matplotlib", "joblib", "scipy"}      # not installed in the browser (stlite/Pyodide) Space


@pytest.fixture(scope="module")
def sync_hf():
    spec = importlib.util.spec_from_file_location("sync_hf", config.ROOT / "app" / "hf_space" / "sync_hf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def portable(tmp_path_factory):
    return save_portable(load_bundle(), tmp_path_factory.mktemp("p") / "current_portable.npz")


def test_model_repo_is_complete(sync_hf, portable):
    files = sync_hf.model_files(portable)
    needed = {"README.md", "requirements.txt", "models/current.joblib", "models/current_portable.npz",
              "data/f107_history.csv", "src/__init__.py", "src/config.py", "src/features.py", "src/predict.py",
              "src/portable.py", "src/ingest/__init__.py", "src/ingest/fetch_live.py"}
    assert needed <= set(files)
    assert all(path.exists() for path in files.values())


def test_space_build_has_every_file_the_app_loads(sync_hf, portable, tmp_path):
    files = sync_hf.build_space(tmp_path, portable)
    assert all(path.exists() for path in files.values())
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    listed = json.loads(re.search(r"Object\.fromEntries\((\[.*?\])\.map", page).group(1))
    assert set(listed) == set(files) - {"index.html", "README.md"}
    app = (config.ROOT / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    loaded = re.findall(r'ROOT / "([^"]+)" / "([^"]+)"(?: / "([^"]+)")?', app)
    for parts in loaded:
        assert "/".join(p for p in parts if p) in listed, parts


def _top_level_imports(path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:                                   # module level only; lazy imports inside functions are fine
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_browser_app_needs_no_heavy_packages():
    """Everything the dashboard imports at module level must work without scikit-learn/matplotlib/joblib."""
    modules = ["app/streamlit_app.py", "src/config.py", "src/features.py", "src/predict.py", "src/portable.py",
               "src/scoring.py", "src/ingest/fetch_live.py"]
    for rel in modules:
        assert not _top_level_imports(config.ROOT / rel) & HEAVY, rel


def test_every_deployment_pins_the_training_sklearn():
    """Streamlit (root requirements.txt) and the HF model repo must install the exact training scikit-learn."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bundle = load_bundle()                          # raises if the local version differs
    pin = f"scikit-learn=={bundle['sklearn_version']}"
    assert bundle["sklearn_version"] == sklearn.__version__
    for req in [config.ROOT / "requirements.txt", config.ROOT / "app" / "hf_space" / "requirements.txt"]:
        assert pin in req.read_text(encoding="utf-8").splitlines(), req
