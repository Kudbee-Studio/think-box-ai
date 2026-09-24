"""Replay POST /run steps (PR #184 F20)."""
from __future__ import annotations
from typing import Any
from thinkbox.think_job_post_run_deepen.payload_schema import validate_run_payload

def replay_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    for step in steps:
        body = step.get("body") or {}
        v = validate_run_payload(body)
        if not v["valid"]:
            return {"verification": {"valid": False}, "live_api_called": False}
    return {"verification": {"valid": True, "steps": len(steps)}, "live_api_called": False}
