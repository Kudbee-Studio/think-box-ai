"""Bridge to run_receipts persistence (PR #184 F15)."""
from __future__ import annotations
from typing import Any

def bridge_summary() -> dict[str, Any]:
    return {"module": "backend.api.v1.run_receipts", "hermetic": True, "live_api_called": False}
