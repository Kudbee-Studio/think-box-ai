"""EXP16: energy_free_flow_regulator expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    loop = EnergyLoop.open("e-8", capacity_units=100.0)
    for _ in range(4):
        loop.deposit(1.0)
    return {"pack_id": "EXP16", "ok": loop.free_flow_rate() > 0, "live_api_called": False}
