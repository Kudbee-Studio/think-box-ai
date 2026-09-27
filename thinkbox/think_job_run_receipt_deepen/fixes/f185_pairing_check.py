"""FIX13: PR #185 gate pairing."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.f185_pairing import pairing_ok
    return {"fix_id": "FIX13", "ok": pairing_ok(), "live_api_called": False}
