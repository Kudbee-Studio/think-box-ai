"""EXP03: long_range_hop_budget expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink

def activate_pack() -> dict[str, object]:
    link = LongRangeLink.open("lr-3", max_hops=2)
    link.advance_hop("c1")
    link.advance_hop("c2")
    return {"pack_id": "EXP03", "ok": link.hops == 2, "live_api_called": False}
