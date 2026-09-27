"""Dry-run POST /run flow (PR #184 F17)."""
from __future__ import annotations
from typing import Any
from thinkbox.think_job_post_run_deepen.fixtures import load_fixture
from thinkbox.think_job_post_run_deepen.payload_schema import validate_run_payload

def dry_run_post_run(goal: str = "hermetic goal") -> dict[str, Any]:
    body = {"goal": goal, "agent_id": "agent-hermetic", "governance_token": "tok-hermetic"}
    validation = validate_run_payload(body)
    sample = load_fixture("sample_run_response.json")
    return {"dry_run": True, "validation": validation, "response": sample, "live_api_called": False}
