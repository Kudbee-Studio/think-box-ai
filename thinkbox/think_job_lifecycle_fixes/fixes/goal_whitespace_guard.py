"""FIX06: Reject whitespace-only goal strings."""
from __future__ import annotations
from typing import Any

def goal_valid(goal: str | None) -> bool:
    return bool(goal and goal.strip())

def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX06",
        "empty_rejected": not goal_valid("   "),
        "valid_ok": goal_valid("poll status"),
        "live_api_called": False,
    }
