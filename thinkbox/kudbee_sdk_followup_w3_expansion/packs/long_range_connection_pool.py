"""EXP08: long_range_connection_pool expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangePool

def activate_pack() -> dict[str, object]:
    pool = LongRangePool()
    pool.acquire("a")
    pool.acquire("b")
    return {"pack_id": "EXP08", "ok": len(pool.links) == 2, "live_api_called": False}
