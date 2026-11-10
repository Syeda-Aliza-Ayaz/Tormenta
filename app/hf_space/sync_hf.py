"""Publish Tormenta on Hugging Face (both free): a model repo and a live static Space.

Model repo   <user>/tormenta — README.md (model card), models/current.joblib + current_portable.npz, src/**,
                               data/f107_history.csv, requirements.txt
Static Space <user>/tormenta — the Streamlit app running in the visitor's browser (stlite on Pyodide): index.html,
                               app/streamlit_app.py, src/**, models/current_portable.npz, data + report assets.
Hosted Gradio/Docker Spaces need HF PRO; a static Space is free and still runs the real app live.

Auth: HF_TOKEN environment variable (a *write* token), or a prior `hf auth login`.

    .venv\\Scripts\\python app\\hf_space\\sync_hf.py --user <hf-username>
    .venv\\Scripts\\python app\\hf_space\\sync_hf.py --build-only <dir>     # build the Space locally, upload nothing
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.portable import save_portable  # noqa: E402
from src.predict import load_bundle  # noqa: E402

HERE = Path(__file__).parent
# Pyodide packages the browser app needs (no scikit-learn: the model is the portable .npz, scores use numpy)
BROWSER_REQUIREMENTS = ["numpy", "pandas", "altair", "requests"]
SPACE_ASSETS = ["app/streamlit_app.py", "data/f107_history.csv", "reports/metrics/test.csv",
                "forecasts/log.csv", "forecasts/scores.csv", "forecasts/recent.csv", "forecasts/noaa_live.csv",
                "reports/figures/14_may2024_nowcast.png"]


def _src_files() -> dict:
    return {p.relative_to(ROOT).as_posix(): p for p in sorted((ROOT / "src").rglob("*.py"))}


def model_files(portable: Path) -> dict:
    """Model-repo path → local path."""
    return {"README.md": HERE / "model_card.md", "requirements.txt": HERE / "requirements.txt",
            "models/current.joblib": ROOT / "models" / "current.joblib",
            "models/current_portable.npz": portable,
            "data/f107_history.csv": ROOT / "data" / "f107_history.csv", **_src_files()}


def build_space(dest: Path, portable: Path) -> dict:
    """Write the complete static Space into dest; returns Space path → local path."""
    files = {p: ROOT / p for p in SPACE_ASSETS}
    files.update(_src_files())
    files["models/current_portable.npz"] = portable
    app_files = sorted(files)
    page = (HERE / "space" / "index.html").read_text(encoding="utf-8")
    page = page.replace("__FILES__", json.dumps(app_files)).replace("__REQUIREMENTS__", json.dumps(BROWSER_REQUIREMENTS))
    for rel, src in files.items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest / rel)
    (dest / "index.html").write_text(page, encoding="utf-8")
    shutil.copyfile(HERE / "space" / "README.md", dest / "README.md")
    return {rel: dest / rel for rel in [*app_files, "index.html", "README.md"]}


def _push(api, repo_id, repo_type, files, message, **create):
    from huggingface_hub import CommitOperationAdd
    api.create_repo(repo_id, repo_type=repo_type, exist_ok=True, **create)
    ops = [CommitOperationAdd(path_in_repo=dest, path_or_fileobj=str(src)) for dest, src in files.items()]
    api.create_commit(repo_id, repo_type=repo_type, operations=ops, commit_message=message)


def sync(user: str, message: str) -> list[str]:
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ.get("HF_TOKEN"))
    repo = f"{user}/tormenta"
    with tempfile.TemporaryDirectory() as tmp:
        portable = save_portable(load_bundle(), Path(tmp) / "current_portable.npz")
        _push(api, repo, "model", model_files(portable), message)
        _push(api, repo, "space", build_space(Path(tmp) / "space", portable), message, space_sdk="static")
    return [f"https://huggingface.co/{repo}", f"https://huggingface.co/spaces/{repo}"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", help="Hugging Face username, e.g. aliza-ayaz")
    ap.add_argument("--message", default="Sync Tormenta model and live Space")
    ap.add_argument("--build-only", type=Path, help="build the Space into this folder and stop")
    args = ap.parse_args()
    if args.build_only:
        args.build_only.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            files = build_space(args.build_only, save_portable(load_bundle(), Path(tmp) / "current_portable.npz"))
        print(f"built {len(files)} files in {args.build_only}")
    else:
        print("\n".join(sync(args.user, args.message)))
