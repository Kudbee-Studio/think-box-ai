"""FIX12: F133 e2e harness file exists."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.f133_harness import f133_test_present
    return {"fix_id": "FIX12", "present": f133_test_present(), "live_api_called": False}
