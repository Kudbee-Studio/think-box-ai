"""FIX16: receipt stub hermetic."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.receipt_stub import emit_run_receipt
    r = emit_run_receipt("job-hermetic", "rcpt-hermetic")
    return {"fix_id": "FIX16", "ok": r.get("receipt_id") == "rcpt-hermetic", "live_api_called": False}
