"""Hermetic fixtures for SDK demos (PR #179 F17)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

FIXTURES_DIR = Path("data/kudbee_sdk/fixtures")


def fixture_path(name: str) -> Path:
    return REPO_ROOT / FIXTURES_DIR / name


def load_fixture(name: str) -> dict[str, Any]:
    path = fixture_path(name)
    return json.loads(path.read_text(encoding="utf-8"))
