"""FIX22: Four-state flags honest on status report."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.integrate import integration_summary

    r = integration_summary()
    return {
        "fix_id": "FIX22",
        "ok": r["live_verified"] is False and r["live_api_called"] is False,
        "live_api_called": False,
    }
