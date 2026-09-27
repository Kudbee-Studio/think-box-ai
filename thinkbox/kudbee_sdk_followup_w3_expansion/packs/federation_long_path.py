"""EXP22: federation_long_path expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink
from thinkbox.kudbee_sdk_followup_w3.twin_stub import TwinFederationStub

def activate_pack() -> dict[str, object]:
    link = LongRangeLink.open("fed", max_hops=4)
    link.advance_hop("hop-1")
    fed = TwinFederationStub()
    fed.register_peer("remote", "sess")
    return {"pack_id": "EXP22", "ok": link.hops == 1 and fed.federation_snapshot()["peer_count"] == 1, "live_api_called": False}
