"""FIX16: Stream path uses /api/v1/run/."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.stream_receipt_link import stream_path
    p = stream_path("j")["path"]
    return {"fix_id": "FIX16", "ok": p.startswith("/api/v1/run/"), "live_api_called": False}
