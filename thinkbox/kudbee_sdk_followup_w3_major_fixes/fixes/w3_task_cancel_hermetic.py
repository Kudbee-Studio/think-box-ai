"""FIX07: w3_task_cancel_hermetic (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.task_bridge import TaskBridgeW3
    t = TaskBridgeW3.create("t", "n")
    out = t.cancel_hermetic()
    return {"fix_id": "FIX07", "ok": out["status"] == "failed", "live_api_called": False}
