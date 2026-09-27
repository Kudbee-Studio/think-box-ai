"""FIX11: PR #188 governed run major fixes gate."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox import kilo_pr188_think_job_governed_run_major_fixes as pr188
    ok, _ = pr188.validate_fixes_manifest()
    return {"fix_id": "FIX11", "ok": ok, "live_api_called": False}
