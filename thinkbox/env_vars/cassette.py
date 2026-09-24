"""Hermetic env cassettes (PR #200)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

CASSETTE_DIR = Path("data/env_vars/cassettes")


def cassette_path(name: str, repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    return root / CASSETTE_DIR / name


def load_cassette(name: str, repo_root: Path | None = None) -> dict[str, Any]:
    path = cassette_path(name, repo_root)
    return json.loads(path.read_text(encoding="utf-8"))


def cassette_environ(name: str, repo_root: Path | None = None) -> dict[str, str]:
    doc = load_cassette(name, repo_root)
    raw = doc.get("environ") or {}
    return {str(k): str(v) for k, v in raw.items()}
