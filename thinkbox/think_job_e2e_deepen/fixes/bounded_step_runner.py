"""FIX10: Bounded step runner for hermetic job simulations."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.config import load_config_from_env
from thinkbox.think_job_e2e_deepen.job_runner_stub import advance_job, create_job


def run_bounded_steps(job_id: str, steps: tuple[str, ...]) -> dict[str, Any]:
    cfg = load_config_from_env({"THINK_JOB_E2E_DEEPEN_DRY_RUN": "true"})
    cap = cfg.max_job_steps
    job = create_job(job_id)
    spent = 0
    for step in steps:
        if spent >= cap:
            break
        advance_job(job, step)
        spent += 1
    return {
        "job_id": job.job_id,
        "state": job.state,
        "steps_spent": spent,
        "live_api_called": False,
    }


def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX10", **run_bounded_steps("bounded", ("start", "complete"))}
