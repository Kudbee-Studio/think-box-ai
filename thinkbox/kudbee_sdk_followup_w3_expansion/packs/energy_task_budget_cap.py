"""EXP18: energy_task_budget_cap expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop
from thinkbox.kudbee_sdk_followup_w3.task_bridge import TaskBridgeW3

def activate_pack() -> dict[str, object]:
    task = TaskBridgeW3.create("t-e", "energy-cap")
    loop = EnergyLoop.open(task.task.task_id, capacity_units=2.0)
    loop.deposit(2.0)
    return {"pack_id": "EXP18", "ok": loop.conserved(), "live_api_called": False}
