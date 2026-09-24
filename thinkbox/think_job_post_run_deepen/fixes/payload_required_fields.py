from __future__ import annotations
from typing import Any
from thinkbox.think_job_post_run_deepen.payload_schema import validate_run_payload
def apply_fix() -> dict[str, Any]:
    v = validate_run_payload({"goal": "g"})
    return {"fix_id": "FIX01", "valid": v["valid"], "live_api_called": False}
