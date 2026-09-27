from __future__ import annotations
from typing import Any
from thinkbox.think_job_post_run_deepen.governance_stub import bind_governance_fields
def apply_fix() -> dict[str, Any]:
    r = bind_governance_fields("agent", "")
    return {"fix_id": "FIX02", "admitted": r["admitted"], "live_api_called": False}
