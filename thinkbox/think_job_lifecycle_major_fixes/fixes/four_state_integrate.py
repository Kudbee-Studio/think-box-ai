"""FIX21: integration summary honesty."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_lifecycle_major_fixes.integrate import integration_summary
    r = integration_summary()
    return {"fix_id": "FIX21", "ok": r["live_verified"] is False, "live_api_called": False}
