"""FIX14: PR #184 receipt handoff stub reachable."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.enhancements.receipt_handoff_stub import receipt_handoff
    h = receipt_handoff("job1", "rcpt1")
    return {"fix_id": "FIX14", "ok": h.get("handoff") is True, "live_api_called": False}
