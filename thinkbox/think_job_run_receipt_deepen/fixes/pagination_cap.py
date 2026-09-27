"""FIX09: Pagination limit capped at 50."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.pagination_stub import page_slice
    return {"fix_id": "FIX09", "len": len(page_slice(list(range(100)), 50)), "live_api_called": False}
