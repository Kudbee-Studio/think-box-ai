"""FIX32: openapi_version_honesty (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.negotiation import SDK_FOLLOWUP_W3_API_VERSION
    return {"fix_id": "FIX32", "ok": SDK_FOLLOWUP_W3_API_VERSION == 4, "live_api_called": False}
