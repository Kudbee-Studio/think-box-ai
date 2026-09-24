"""FIX10: PR #187 receipt major fixes gate."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox import kilo_pr187_think_job_receipt_major_fixes as pr187
    ok, _ = pr187.validate_fixes_manifest()
    return {"fix_id": "FIX10", "ok": ok, "live_api_called": False}
