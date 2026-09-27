"""FIX21: Four-state on integrate."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_governed_run_fixes.integrate import integration_summary
    s = integration_summary()
    return {"fix_id": "FIX21", "ok": s["live_api_called"] is False, "live_api_called": False}
