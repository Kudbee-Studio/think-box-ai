"""FIX23: Receipt schema rejects incomplete body."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.receipt_schema import validate_receipt_shape
    return {"fix_id": "FIX23", "rejects": not validate_receipt_shape({"receipt_id": "r"}), "live_api_called": False}
