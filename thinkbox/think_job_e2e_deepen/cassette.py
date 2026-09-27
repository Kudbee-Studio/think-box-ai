"""Cassette replay for Think Job lifecycle flows (PR #183 F09)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


@dataclass(frozen=True)
class JobCassette:
    name: str
    steps: tuple[dict[str, Any], ...]


def cassette_path(name: str, repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    safe = name.replace("..", "").replace("/", "_")
    if safe.endswith(".json"):
        safe = safe[:-5]
    return root / "data/think_job/cassettes" / f"{safe}.json"


def load_cassette(name: str, repo_root: Path | None = None) -> JobCassette:
    path = cassette_path(name, repo_root)
    doc = json.loads(path.read_text(encoding="utf-8"))
    steps = tuple(dict(s) for s in (doc.get("steps") or []))
    return JobCassette(name=name, steps=steps)


def replay_cassette(name: str, repo_root: Path | None = None) -> dict[str, Any]:
    tape = load_cassette(name, repo_root)
    return {
        "cassette": tape.name,
        "step_count": len(tape.steps),
        "steps": list(tape.steps),
        "replayed": True,
        "live_api_called": False,
    }
