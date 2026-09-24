"""Export manifest for Think Job deepen artifacts (PR #183 F22)."""

from __future__ import annotations

from typing import Any


def export_manifest() -> dict[str, Any]:
    return {
        "manifest_version": 1,
        "artifacts": [
            "data/think_job/pr183_features.json",
            "data/think_job/pr183_fixes.json",
            "data/think_job/pr183_checklist.json",
            "data/think_job/cassettes/job_lifecycle_flow.json",
            "data/think_job/fixtures/sample_job_status.json",
        ],
        "live_api_called": False,
    }
