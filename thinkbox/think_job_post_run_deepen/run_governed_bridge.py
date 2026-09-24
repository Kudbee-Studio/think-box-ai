"""Bridge to run_governed module (PR #184 F14)."""
from __future__ import annotations
from typing import Any

def bridge_summary() -> dict[str, Any]:
    return {"module": "backend.api.v1.run_governed", "hermetic": True, "live_api_called": False}
