"""FIX15: Status path uses /api/v1/run/job/."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.status_receipt_link import status_path
    p = status_path("j")["path"]
    return {"fix_id": "FIX15", "ok": "/api/v1/run/job/" in p, "live_api_called": False}
