"""Fixture loader (PR #184 F10)."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def load_fixture(name: str, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    safe = name.replace("..", "").replace("/", "_")
    if not safe.endswith(".json"):
        safe += ".json"
    return json.loads((root / "data/think_job_post_run/fixtures" / safe).read_text(encoding="utf-8"))
