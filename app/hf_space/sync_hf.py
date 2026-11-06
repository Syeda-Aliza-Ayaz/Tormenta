"""Upload the Gradio demo to a Hugging Face Space (creates it on the first run).

Space layout:  app.py, README.md (model card), requirements.txt, src/**, models/current.joblib,
               data/f107_history.csv
Auth: HF_TOKEN environment variable (a *write* token), or a prior `hf auth login`.

    .venv\\Scripts\\python app\\hf_space\\sync_hf.py --space <hf-username>/tormenta
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from huggingface_hub import CommitOperationAdd, HfApi  # noqa: E402

HERE = Path(__file__).parent


def files_to_upload() -> dict:
    """Space path → local path."""
    files = {"app.py": HERE / "app.py", "README.md": HERE / "README.md",
             "requirements.txt": HERE / "requirements.txt",
             "models/current.joblib": ROOT / "models" / "current.joblib",
             "data/f107_history.csv": ROOT / "data" / "f107_history.csv"}
    for path in sorted((ROOT / "src").rglob("*.py")):
        files[path.relative_to(ROOT).as_posix()] = path
    return files


def sync(space: str, message: str) -> str:
    api = HfApi(token=os.environ.get("HF_TOKEN"))
    api.create_repo(space, repo_type="space", space_sdk="gradio", exist_ok=True)
    ops = [CommitOperationAdd(path_in_repo=dest, path_or_fileobj=str(src)) for dest, src in files_to_upload().items()]
    api.create_commit(space, repo_type="space", operations=ops, commit_message=message)
    return f"https://huggingface.co/spaces/{space}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True, help="e.g. your-hf-username/tormenta")
    ap.add_argument("--message", default="Sync Tormenta app and model")
    print(sync(**vars(ap.parse_args())))
