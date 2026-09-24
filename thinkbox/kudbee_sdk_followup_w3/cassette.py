"""Cassette replay for wave 3 SDK flows (PR #191 F09)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

_CASSETTE_DIR = REPO_ROOT / "data/kudbee_sdk/cassettes/w3"


def load_cassette(name: str) -> dict[str, Any]:
    path = _CASSETTE_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def replay_cassette(name: str) -> dict[str, Any]:
    tape = load_cassette(name)
    steps = list(tape.get("steps") or [])
    return {
        "cassette": name,
        "step_count": len(steps),
        "steps": steps,
        "live_api_called": False,
        "dry_run": True,
    }
