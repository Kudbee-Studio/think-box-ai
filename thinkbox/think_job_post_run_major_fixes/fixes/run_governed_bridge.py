"""FIX05: run_governed bridge hermetic."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.run_governed_bridge import bridge_summary
    s = bridge_summary()
    return {"fix_id": "FIX05", "ok": s.get("hermetic") is True, "live_api_called": False}
