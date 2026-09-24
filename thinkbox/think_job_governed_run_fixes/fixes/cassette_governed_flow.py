"""FIX15: Governed run fix cassette."""
from __future__ import annotations
import json
from typing import Any
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def apply_fix() -> dict[str, Any]:
    path = REPO_ROOT / "data/think_job_governed_run/cassettes/governed_run_fix_flow.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {"fix_id": "FIX15", "steps": len(doc.get("steps") or []), "live_api_called": False}
