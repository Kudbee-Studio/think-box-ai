"""FIX13: payload schema validation."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.payload_schema import validate_run_payload
    bad = validate_run_payload({})
    good = validate_run_payload({"goal": "g", "agent_id": "a", "governance_token": "t"})
    return {"fix_id": "FIX13", "ok": not bad["valid"] and good["valid"], "live_api_called": False}
