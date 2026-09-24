"""FIX10: Cassette replay includes 401 auth branch."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kilo_live_proof_readiness import REPO_ROOT
    path = REPO_ROOT / "data/think_job_post_run/cassettes/post_run_auth_flow.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    has_401 = any(step.get("status") == 401 for step in body.get("steps", []))
    return {"fix_id": "FIX10", "cassette_exists": path.is_file(), "has_401": has_401, "live_api_called": False}
