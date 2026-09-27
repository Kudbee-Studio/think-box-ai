"""EXP04: long_range_correlation_chain expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink

def activate_pack() -> dict[str, object]:
    link = LongRangeLink.open("lr-4")
    link.advance_hop("corr-a")
    return {"pack_id": "EXP04", "ok": link.correlation_ids == ["corr-a"], "live_api_called": False}
