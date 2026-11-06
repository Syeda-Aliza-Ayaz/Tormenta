"""Publish Tormenta on Hugging Face (both free): a model repo and a static landing-page Space.

Model repo  <user>/tormenta  — README.md (model card), models/current.joblib, src/**, data/f107_history.csv,
                               requirements.txt
Static Space <user>/tormenta — index.html, README.md, figures/*.png (links to the live Streamlit app)
Hosting a Gradio Space now needs HF PRO, so the Gradio app (app.py) is run locally instead.

Auth: HF_TOKEN environment variable (a *write* token), or a prior `hf auth login`.

    .venv\\Scripts\\python app\\hf_space\\sync_hf.py --user <hf-username>
"""
import argparse
import os
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
SPACE_FIGURES = ["14_may2024_nowcast.png", "11_error_by_level.png", "16_live_nowcast.png"]


def model_files() -> dict:
    """Model-repo path → local path."""
    files = {"README.md": HERE / "model_card.md", "requirements.txt": HERE / "requirements.txt",
             "models/current.joblib": ROOT / "models" / "current.joblib",
             "data/f107_history.csv": ROOT / "data" / "f107_history.csv"}
    for path in sorted((ROOT / "src").rglob("*.py")):
        files[path.relative_to(ROOT).as_posix()] = path
    return files


def space_files() -> dict:
    """Static-Space path → local path."""
    files = {"index.html": HERE / "space" / "index.html", "README.md": HERE / "space" / "README.md"}
    for name in SPACE_FIGURES:
        files[f"figures/{name}"] = ROOT / "reports" / "figures" / name
    return files


def _push(api, repo_id, repo_type, files, message, **create):
    api.create_repo(repo_id, repo_type=repo_type, exist_ok=True, **create)
    ops = [CommitOperationAdd(path_in_repo=dest, path_or_fileobj=str(src)) for dest, src in files.items()]
    api.create_commit(repo_id, repo_type=repo_type, operations=ops, commit_message=message)


def sync(user: str, message: str) -> list[str]:
    api = HfApi(token=os.environ.get("HF_TOKEN"))
    repo = f"{user}/tormenta"
    _push(api, repo, "model", model_files(), message)
    _push(api, repo, "space", space_files(), message, space_sdk="static")
    return [f"https://huggingface.co/{repo}", f"https://huggingface.co/spaces/{repo}"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="Hugging Face username, e.g. aliza-ayaz")
    ap.add_argument("--message", default="Sync Tormenta model and landing page")
    print("\n".join(sync(**vars(ap.parse_args()))))
