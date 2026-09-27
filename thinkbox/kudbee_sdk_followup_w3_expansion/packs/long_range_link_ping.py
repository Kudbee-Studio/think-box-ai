"""EXP02: long_range_link_ping expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink

def activate_pack() -> dict[str, object]:
    return {"pack_id": "EXP02", "ok": LongRangeLink.open("lr-2").ping()["reachable"], "live_api_called": False}
