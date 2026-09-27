"""FIX17: gate id honesty."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_major_fixes.negotiation import GATE_ID
    return {"fix_id": "FIX17", "ok": GATE_ID == "think-job-post-run-major-fixes", "live_api_called": False}
