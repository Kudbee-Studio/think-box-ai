"""Deterministic replay (PR #186 F20)."""
from __future__ import annotations
from typing import Any
from thinkbox.think_job_run_receipt_deepen.receipt_schema import validate_receipt_shape

def replay_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    for step in steps:
        body = step.get("receipt") or {}
        if body and not validate_receipt_shape(body):
            return {"valid": False, "live_api_called": False}
    return {"valid": True, "count": len(steps), "live_api_called": False}
