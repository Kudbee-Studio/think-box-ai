"""FIX34: w3_major_run_all_helper (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.integrate import run_feature_demo
    r = run_feature_demo("health")
    return {"fix_id": "FIX34", "ok": r.get("ready") is True, "live_api_called": False}
