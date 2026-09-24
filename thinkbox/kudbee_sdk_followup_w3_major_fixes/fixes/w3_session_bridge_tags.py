"""FIX06: w3_session_bridge_tags (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.session_bridge import SessionBridgeW3
    s = SessionBridgeW3.open("s")
    s.set_tag("lane", "hermetic")
    return {"fix_id": "FIX06", "ok": s.tags.get("lane") == "hermetic", "live_api_called": False}
