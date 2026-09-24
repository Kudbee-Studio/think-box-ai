"""Feature registry (PR #184 F24)."""
from __future__ import annotations
from typing import Any
from thinkbox.think_job_post_run_deepen.cassette import replay_cassette
from thinkbox.think_job_post_run_deepen.dry_run import dry_run_post_run
from thinkbox.think_job_post_run_deepen.negotiation import THINK_JOB_POST_RUN_DEEPEN_VERSION

def run_feature_demo(feature_id: str) -> dict[str, Any]:
    if feature_id == "cassette":
        return replay_cassette("post_run_flow.json")
    if feature_id == "dry_run":
        return dry_run_post_run()
    return {"error": "unknown", "feature_id": feature_id, "live_api_called": False}

def integration_summary() -> dict[str, Any]:
    return {
        "think_job_post_run_deepen_version": THINK_JOB_POST_RUN_DEEPEN_VERSION,
        "live_api_called": False,
        "dry_run": True,
    }
