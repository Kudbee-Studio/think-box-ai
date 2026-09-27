"""EXP07: long_range_backoff_curve expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink

def activate_pack() -> dict[str, object]:
    link = LongRangeLink.open("lr-7", max_hops=1)
    link.advance_hop("x")
    link.advance_hop("y")
    return {"pack_id": "EXP07", "ok": not link.ping()["reachable"], "live_api_called": False}
