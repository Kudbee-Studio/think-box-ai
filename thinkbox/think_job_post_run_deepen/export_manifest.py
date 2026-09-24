"""Export manifest (PR #184 F22)."""
from __future__ import annotations
from typing import Any

def export_manifest() -> dict[str, Any]:
    return {
        "artifacts": [
            "data/think_job_post_run/pr184_features.json",
            "data/think_job_post_run/cassettes/post_run_flow.json",
        ],
        "live_api_called": False,
    }
