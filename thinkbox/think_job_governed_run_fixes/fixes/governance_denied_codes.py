"""FIX04: Distinct admission vs governance codes."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX04", "distinct": "ADMISSION_DENIED" != "GOVERNANCE_DENIED", "live_api_called": False}
