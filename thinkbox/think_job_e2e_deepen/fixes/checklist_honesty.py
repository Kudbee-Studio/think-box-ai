"""FIX16: Validate PR #183 checklist honesty."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def validate_checklist(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    path = root / "data/think_job/pr183_checklist.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    ok = doc.get("live_verified") is False and doc.get("live_api_called") is False
    missing = [
        rel for rel in doc.get("required_artifacts", []) if not (root / str(rel)).is_file()
    ]
    return {
        "valid": ok and not missing,
        "missing_artifacts": missing,
        "live_api_called": False,
    }


def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX16", **validate_checklist()}
