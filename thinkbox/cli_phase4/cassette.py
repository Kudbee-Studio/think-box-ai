"""Offline replay / cassette library for CLI paths (PR #196 F07)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_live_proof_readiness import REPO_ROOT


@dataclass(frozen=True)
class CassetteEntry:
    name: str
    request: dict[str, Any]
    response: dict[str, Any]


def cassette_path(name: str, repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    safe = name.replace("..", "").replace("/", "_")
    return root / "data/cli_phase4/cassettes" / f"{safe}.json"


def load_cassette(name: str, repo_root: Path | None = None) -> CassetteEntry:
    path = cassette_path(name, repo_root)
    doc = json.loads(path.read_text(encoding="utf-8"))
    return CassetteEntry(
        name=name,
        request=dict(doc.get("request") or {}),
        response=dict(doc.get("response") or {}),
    )


def replay_cassette(name: str, repo_root: Path | None = None) -> dict[str, Any]:
    entry = load_cassette(name, repo_root)
    out = dict(entry.response)
    out["replayed"] = True
    out["cassette"] = entry.name
    out["live_api_called"] = False
    return out
