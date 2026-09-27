"""FIX17: Dry run skips persistence."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.dry_run import dry_run_skips_persist
    return {"fix_id": "FIX17", "ok": dry_run_skips_persist(True), "live_api_called": False}
