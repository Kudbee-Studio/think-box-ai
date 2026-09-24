"""Feature registry integration (PR #183 F24)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.cassette import replay_cassette
from thinkbox.think_job_e2e_deepen.dry_run import dry_run_job_lifecycle
from thinkbox.think_job_e2e_deepen.job_runner_stub import create_job, advance_job
from thinkbox.think_job_e2e_deepen.negotiation import THINK_JOB_E2E_DEEPEN_VERSION
from thinkbox.think_job_e2e_deepen.receipt_bind import bind_receipt_to_job
from thinkbox.think_job_e2e_deepen.replay import replay_actions

_FEATURE_HANDLERS: dict[str, str] = {
    "cassette": "replay_cassette",
    "dry_run": "dry_run_job_lifecycle",
    "runner": "advance_job",
    "receipt_bind": "bind_receipt_to_job",
    "replay": "replay_actions",
}


def list_registered_features() -> tuple[str, ...]:
    return tuple(sorted(_FEATURE_HANDLERS.keys()))


def run_feature_demo(feature_id: str) -> dict[str, Any]:
    if feature_id == "cassette":
        return replay_cassette("job_lifecycle_flow.json")
    if feature_id == "dry_run":
        return dry_run_job_lifecycle()
    if feature_id == "runner":
        job = create_job("demo-job")
        return advance_job(job, "start")
    if feature_id == "receipt_bind":
        return bind_receipt_to_job("rcpt-demo", "job-demo")
    if feature_id == "replay":
        return replay_actions([{"step": "start"}, {"step": "complete"}])
    return {"error": "unknown_feature", "feature_id": feature_id, "live_api_called": False}


def integration_summary() -> dict[str, Any]:
    from thinkbox.think_job_e2e_deepen.deepen_status_report import route_catalog_deepen

    return {
        "think_job_e2e_deepen_version": THINK_JOB_E2E_DEEPEN_VERSION,
        "registered_features": list(list_registered_features()),
        "routes": route_catalog_deepen(),
        "live_api_called": False,
        "dry_run": True,
    }
