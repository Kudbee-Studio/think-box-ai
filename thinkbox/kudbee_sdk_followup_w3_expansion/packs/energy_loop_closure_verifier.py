"""EXP15: energy_loop_closure_verifier expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    loop = EnergyLoop.open("e-7", capacity_units=1.0)
    loop.deposit(1.0)
    return {"pack_id": "EXP15", "ok": loop.conserved() and loop.flow_units == loop.capacity_units, "live_api_called": False}
