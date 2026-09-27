"""FIX16: Jobs digest multiplex UI helper."""
from __future__ import annotations
from typing import Any
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def apply_fix() -> dict[str, Any]:
    ok = (REPO_ROOT / "public/control-plane/think_job_status_client.js").is_file()
    return {"fix_id": "FIX16", "ok": ok, "live_api_called": False}
