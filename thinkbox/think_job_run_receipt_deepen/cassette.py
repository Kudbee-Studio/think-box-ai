"""Cassette replay (PR #186 F10)."""
from __future__ import annotations
import json
from pathlib import Path
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def replay_cassette(name: str) -> dict[str, object]:
    path = REPO_ROOT / "data/think_job_run_receipt/cassettes" / name
    doc = json.loads(path.read_text(encoding="utf-8"))
    steps = list(doc.get("steps") or [])
    return {"step_count": len(steps), "steps": steps, "live_api_called": False}
