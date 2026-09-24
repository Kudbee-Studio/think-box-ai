"""FIX19: lr_energy_loop_mesh_fix (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:

    from thinkbox.kudbee_sdk_longrange_energy.energy_loop_mesh import EnergyLoopMesh
    mesh = EnergyLoopMesh("fix-mesh")
    mesh.attach_loop("l1")
    ok = mesh.snapshot()["loop_count"] == 1

    return {"fix_id": "FIX19", "ok": ok, "live_api_called": False}
