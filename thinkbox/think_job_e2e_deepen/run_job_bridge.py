"""Bridge to run job status schema (PR #183 F19)."""

from __future__ import annotations

from typing import Any


def run_job_bridge_summary() -> dict[str, Any]:
    from thinkbox.think_job_e2e_deepen.fixes.lazy_run_job_schema import resolve_status_schema_version

    return {
        "status_schema_version": resolve_status_schema_version(),
        "surface": "backend/api/v1/run_job_status",
        "hermetic": True,
        "live_api_called": False,
    }
