"""FIX02: POST /run deepen integration honesty."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.integrate import integration_summary
    r = integration_summary()
    return {"fix_id": "FIX02", "ok": r.get("live_verified") is False, "live_api_called": False}
