"""Cassette replay (PR #184 F09)."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def replay_cassette(name: str, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root if repo_root is not None else REPO_ROOT
    safe = name.replace("..", "").replace("/", "_").removesuffix(".json")
    path = root / "data/think_job_post_run/cassettes" / f"{safe}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    steps = list(doc.get("steps") or [])
    return {"cassette": safe, "step_count": len(steps), "steps": steps, "live_api_called": False}
