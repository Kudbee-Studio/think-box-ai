"""DEP03: mesh_loop_coupling deepen pack (PR #193)."""
from __future__ import annotations


def activate_pack() -> dict[str, object]:

    from thinkbox.kudbee_sdk_longrange_energy.energy_loop_mesh import EnergyLoopMesh
    mesh = EnergyLoopMesh("dep-mesh")
    mesh.attach_loop("l1", capacity=10.0)
    ok = mesh.snapshot()["loop_count"] == 1

    return {"pack_id": "DEP03", "ok": ok, "live_api_called": False}
