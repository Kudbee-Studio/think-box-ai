"""Admission gate stub (PR #184 F08)."""
from __future__ import annotations
from typing import Any

def admission_decision(token_present: bool) -> dict[str, Any]:
    return {"allowed": token_present, "reason": "token_required" if not token_present else "ok", "live_api_called": False}
