"""EXP01: long_range_link_open expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink

def activate_pack() -> dict[str, object]:
    link = LongRangeLink.open("lr-1")
    return {"pack_id": "EXP01", "ok": link.link_id == "lr-1", "live_api_called": False}
