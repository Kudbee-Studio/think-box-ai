"""FIX11: Cancel only from non-terminal states."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.lifecycle_catalog import can_transition


def cancel_allowed(state: str) -> bool:
    return can_transition(state, "CANCELLED")


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX11",
        "running_cancel": cancel_allowed("RUNNING"),
        "complete_cancel": cancel_allowed("COMPLETE"),
        "live_api_called": False,
    }
