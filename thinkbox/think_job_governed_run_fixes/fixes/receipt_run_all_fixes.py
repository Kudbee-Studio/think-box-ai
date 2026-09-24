"""FIX19: PR #187 run_all_fixes hermetic."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.fixes.fix_registry import run_all_fixes
    r = run_all_fixes()
    return {"fix_id": "FIX19", "ok": r["fix_count"] == 25 and r["all_hermetic"], "live_api_called": False}
