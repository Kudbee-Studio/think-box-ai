"""Feature registry (PR #184 F24)."""
from __future__ import annotations
from typing import Any
from thinkbox.think_job_post_run_deepen.cassette import replay_cassette
from thinkbox.think_job_post_run_deepen.dry_run import dry_run_post_run
from thinkbox.think_job_post_run_deepen.negotiation import THINK_JOB_POST_RUN_DEEPEN_VERSION
from thinkbox.think_job_post_run_deepen.response_envelope import success_envelope

def run_feature_demo(feature_id: str) -> dict[str, Any]:
    if feature_id == "cassette":
        return replay_cassette("post_run_flow.json")
    if feature_id == "cassette_auth":
        return replay_cassette("post_run_auth_flow.json")
    if feature_id == "dry_run":
        return dry_run_post_run()
    if feature_id == "envelope":
        return success_envelope("job-demo", "rcpt-demo")
    return {"error": "unknown", "feature_id": feature_id, "live_api_called": False}


def list_registered_features() -> tuple[str, ...]:
    return ("cassette", "cassette_auth", "dry_run", "envelope")


def integration_summary() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.route_catalog import route_catalog_summary

    return {
        "think_job_post_run_deepen_version": THINK_JOB_POST_RUN_DEEPEN_VERSION,
        "registered_features": list(list_registered_features()),
        "routes": route_catalog_summary(),
        "live_api_called": False,
        "dry_run": True,
    }
