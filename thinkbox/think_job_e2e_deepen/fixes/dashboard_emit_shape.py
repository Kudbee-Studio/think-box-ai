"""FIX03: Validate Think Job dashboard emission shape (hermetic)."""

from __future__ import annotations

from typing import Any

from thinkbox.dashboard_state import DashboardCategory, DashboardEvent


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX03",
        "category": DashboardCategory.THINK_JOBS.value,
        "event": DashboardEvent.JOB_CREATED.value,
        "live_api_called": False,
    }
