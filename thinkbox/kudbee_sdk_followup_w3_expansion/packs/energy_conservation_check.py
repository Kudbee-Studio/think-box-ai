"""EXP12: energy_conservation_check expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    loop = EnergyLoop.open("e-4", capacity_units=5.0)
    loop.deposit(4.0)
    return {"pack_id": "EXP12", "ok": loop.conserved(), "live_api_called": False}
