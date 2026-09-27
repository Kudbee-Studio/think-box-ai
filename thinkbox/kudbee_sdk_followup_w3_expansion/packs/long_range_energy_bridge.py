"""EXP20: long_range_energy_bridge expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop
from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink

def activate_pack() -> dict[str, object]:
    link = LongRangeLink.open("bridge")
    loop = EnergyLoop.open("bridge-loop")
    loop.deposit(1.0)
    return {"pack_id": "EXP20", "ok": link.ping()["reachable"] and loop.conserved(), "live_api_called": False}
