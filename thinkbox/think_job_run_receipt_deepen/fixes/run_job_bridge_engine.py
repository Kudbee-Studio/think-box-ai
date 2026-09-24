"""FIX20: Run job bridge reads engine_id."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.run_job_bridge import bridge_job_id
    return {"fix_id": "FIX20", "ok": bridge_job_id({"engine_id": "e1"}) == "e1", "live_api_called": False}
