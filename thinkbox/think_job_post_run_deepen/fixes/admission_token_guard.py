from __future__ import annotations
from typing import Any
from thinkbox.think_job_post_run_deepen.admission_stub import admission_decision
def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX04", **admission_decision(False), "live_api_called": False}
