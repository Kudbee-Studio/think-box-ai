"""FIX13: Background task stub pending_count."""
from __future__ import annotations
from typing import Any

def pending_count(tasks: list[str]) -> int:
    return len(tasks)

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX13", "pending": pending_count(["a", "b"]), "live_api_called": False}
