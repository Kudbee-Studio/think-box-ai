"""EXP21: twin_energy_receipt_stub expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3.twin_stub import TwinFederationStub
from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    twin = TwinFederationStub()
    twin.register_peer("t", "s")
    loop = EnergyLoop.open("twin-loop")
    loop.deposit(0.5)
    return {"pack_id": "EXP21", "ok": twin.federation_snapshot()["peer_count"] == 1, "live_api_called": False}
