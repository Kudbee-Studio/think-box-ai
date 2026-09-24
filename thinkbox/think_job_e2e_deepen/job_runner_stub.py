"""Hermetic job-runner stub for e2e deepen (PR #183 F06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HermeticThinkJob:
    job_id: str
    state: str = "PENDING"
    receipt_id: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)


def create_job(job_id: str) -> HermeticThinkJob:
    return HermeticThinkJob(job_id=job_id, state="CONFIGURED")


def advance_job(job: HermeticThinkJob, step: str) -> dict[str, Any]:
    job.steps.append({"step": step, "dry_run": True})
    if step == "complete":
        job.state = "COMPLETE"
    elif step == "fail":
        job.state = "FAILED"
    else:
        job.state = "RUNNING"
    return {
        "job_id": job.job_id,
        "state": job.state,
        "step_count": len(job.steps),
        "live_api_called": False,
    }
