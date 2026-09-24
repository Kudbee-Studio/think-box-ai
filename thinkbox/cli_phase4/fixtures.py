"""Offline fixtures for Phase 4 CLI (PR #196 F07 companion)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def fixture_dir(repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    return root / "data/cli_phase4/fixtures"


def load_fixture(name: str, repo_root: Path | None = None) -> dict[str, Any]:
    path = fixture_dir(repo_root) / name
    return json.loads(path.read_text(encoding="utf-8"))
