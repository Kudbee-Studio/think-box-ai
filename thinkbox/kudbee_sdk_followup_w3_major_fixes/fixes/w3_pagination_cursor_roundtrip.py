"""FIX08: w3_pagination_cursor_roundtrip (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.pagination import decode_cursor, encode_cursor
    payload = {"page": 3}
    return {"fix_id": "FIX08", "ok": decode_cursor(encode_cursor(payload)) == payload, "live_api_called": False}
