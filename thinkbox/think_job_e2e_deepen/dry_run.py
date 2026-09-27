"""Dry-run Think Job page runner (PR #183 F16)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.fixtures import load_fixture
from thinkbox.think_job_e2e_deepen.job_runner_stub import create_job, advance_job


def dry_run_job_lifecycle(job_id: str = "tb_job_hermetic_demo") -> dict[str, Any]:
    job = create_job(job_id)
    advance_job(job, "start")
    advance_job(job, "verify")
    advance_job(job, "complete")
    snapshot = load_fixture("sample_job_status.json")
    return {
        "dry_run": True,
        "job_id": job.job_id,
        "final_state": job.state,
        "fixture_status": snapshot.get("status"),
        "live_api_called": False,
    }


def dry_run_status_page(limit: int = 10) -> dict[str, Any]:
    doc = load_fixture("sample_job_status.json")
    jobs = list(doc.get("jobs") or [])[: max(1, min(limit, 50))]
    return {
        "dry_run": True,
        "jobs": jobs,
        "count": len(jobs),
        "live_api_called": False,
    }
