"""Fixture library for receipt-chain deepen (PR #182 F10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


def fixture_path(name: str, repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    safe = name.replace("..", "").replace("/", "_")
    return root / "data/receipt_chain/fixtures" / safe


def load_fixture(name: str, repo_root: Path | None = None) -> dict[str, Any]:
    path = fixture_path(name, repo_root)
    return json.loads(path.read_text(encoding="utf-8"))
