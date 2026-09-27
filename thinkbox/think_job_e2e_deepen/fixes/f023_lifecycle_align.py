"""FIX04: Align deepen lifecycle with F023 terminal states."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.lifecycle_catalog import can_transition


def apply_fix() -> dict[str, Any]:
    path_ok = (
        can_transition("CONFIGURED", "RUNNING")
        and can_transition("RUNNING", "COMPLETE")
    )
    return {"fix_id": "FIX04", "f023_path_ok": path_ok, "live_api_called": False}
