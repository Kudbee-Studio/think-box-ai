"""Fixture library for wave 2 hermetic tests (PR #181 F10)."""

from __future__ import annotations

import json
from pathlib import Path

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

_FIXTURE_DIR = REPO_ROOT / "data/kudbee_sdk/fixtures/w2"


def load_fixture(name: str) -> dict:
    path = _FIXTURE_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def list_fixture_names() -> tuple[str, ...]:
    if not _FIXTURE_DIR.is_dir():
        return ()
    return tuple(sorted(p.name for p in _FIXTURE_DIR.glob("*.json")))
