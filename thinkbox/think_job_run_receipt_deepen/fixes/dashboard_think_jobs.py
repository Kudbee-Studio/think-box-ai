"""FIX18: Dashboard category THINK_JOBS."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.dashboard_bridge import dashboard_fields
    return {"fix_id": "FIX18", "ok": dashboard_fields()["category"] == "THINK_JOBS", "live_api_called": False}
