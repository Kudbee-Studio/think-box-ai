"""Dashboard JOB_CREATED bridge (PR #184 F12)."""
from __future__ import annotations
from typing import Any
from thinkbox.dashboard_state import DashboardCategory, DashboardEvent

def dashboard_shape() -> dict[str, Any]:
    return {
        "category": DashboardCategory.THINK_JOBS.value,
        "event": DashboardEvent.JOB_CREATED.value,
        "live_api_called": False,
    }
