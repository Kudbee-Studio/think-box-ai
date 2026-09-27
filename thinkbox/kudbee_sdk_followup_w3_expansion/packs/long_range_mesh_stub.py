"""EXP05: long_range_mesh_stub expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangePool

def activate_pack() -> dict[str, object]:
    pool = LongRangePool()
    return {"pack_id": "EXP05", "ok": pool.acquire("m1").link_id == "m1", "live_api_called": False}
