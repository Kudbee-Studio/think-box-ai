"""FIX18: Map think_job_not_found to structured envelope."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_lifecycle_fixes.errors import structured_error
    env = structured_error("think_job_not_found", {"detail": "think_job_not_found"})
    return {"fix_id": "FIX18", "envelope_ok": env["error_type"] == "think_job_not_found", "live_api_called": False}
