"""Best-effort provenance of the backend executing an evaluation."""
import os
from pathlib import Path
import subprocess

from app.core.config import get_settings


def capture_code_version() -> dict:
    supplied = (os.environ.get("RAG_LAB_CODE_COMMIT") or get_settings().code_commit or "").strip()
    if supplied:
        return {"commit": supplied, "dirty": None, "commit_source": "environment"}
    root = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=True, timeout=2,
        ).stdout.strip()
        if not commit:
            raise ValueError("Empty Git revision")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"commit": None, "dirty": None, "commit_source": "unavailable"}
    try:
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root,
            capture_output=True, text=True, check=True, timeout=2,
        ).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        dirty = None
    return {"commit": commit, "dirty": dirty, "commit_source": "git"}
