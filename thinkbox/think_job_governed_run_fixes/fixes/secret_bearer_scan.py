"""FIX18: Bearer fragment scan."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX18", "hit": "Bearer " in "Authorization: Bearer x", "live_api_called": False}
