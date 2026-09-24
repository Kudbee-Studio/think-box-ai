"""FIX15: Lifecycle major-fix cassette."""
from __future__ import annotations
import json
from typing import Any
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def apply_fix() -> dict[str, Any]:
    path = REPO_ROOT / "data/think_job_lifecycle_major/cassettes/lifecycle_major_flow.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    return {"fix_id": "FIX15", "ok": body.get("hermetic") is True, "live_api_called": False}
