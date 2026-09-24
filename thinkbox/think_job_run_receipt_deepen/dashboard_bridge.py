"""Dashboard think job bridge (PR #186 F16)."""
from __future__ import annotations
from typing import Any

def dashboard_fields() -> dict[str, Any]:
    return {"category": "THINK_JOBS", "live_api_called": False}
