"""FIX20: pr177_sdk_app_gate (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kilo_pr177_kudbee_sdk_app import GATE_ID
    return {"fix_id": "FIX20", "ok": GATE_ID == "kudbee-sdk-app", "live_api_called": False}
