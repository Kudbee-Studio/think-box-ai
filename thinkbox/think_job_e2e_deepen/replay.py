"""Deterministic replay of hermetic job actions (PR #183 F12 replay lane)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.job_runner_stub import create_job, advance_job
from thinkbox.think_job_e2e_deepen.lifecycle_catalog import can_transition


def replay_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    job = create_job("replay-job")
    prev = job.state
    for action in actions:
        step = str(action.get("step", "noop"))
        advance_job(job, step)
        to_state = job.state
        if not can_transition(prev, to_state) and prev != to_state:
            return {
                "verification": {"valid": False, "reason": "invalid_transition"},
                "live_api_called": False,
            }
        prev = to_state
    return {
        "verification": {"valid": True, "final_state": job.state},
        "step_count": len(job.steps),
        "live_api_called": False,
    }
