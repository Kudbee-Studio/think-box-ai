"""FIX08: lr_hop_cursor_roundtrip (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:

    from thinkbox.kudbee_sdk_longrange_energy.hop_scheduler import decode_cursor, encode_cursor
    ok = decode_cursor(encode_cursor({"hop": 1}))["hop"] == 1

    return {"fix_id": "FIX08", "ok": ok, "live_api_called": False}
