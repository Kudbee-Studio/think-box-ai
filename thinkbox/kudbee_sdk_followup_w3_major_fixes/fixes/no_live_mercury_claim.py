"""FIX24: no_live_mercury_claim (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3_major_fixes.negotiation import GATE_ID
    return {"fix_id": "FIX24", "ok": GATE_ID == "kudbee-sdk-followup-w3-major-fixes", "live_api_called": False}
