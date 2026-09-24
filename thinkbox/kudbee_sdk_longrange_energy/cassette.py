"""Cassette replay for wave LR-energy deepen SDK flows (PR #193 F09)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT

_CASSETTE_DIR = REPO_ROOT / "data/kudbee_sdk/cassettes/lr_energy"


def load_cassette(name: str) -> dict[str, Any]:
    path = _CASSETTE_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def list_cassette_names() -> tuple[str, ...]:
    if not _CASSETTE_DIR.is_dir():
        return ()
    return tuple(sorted(p.name for p in _CASSETTE_DIR.glob("*.json")))


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
