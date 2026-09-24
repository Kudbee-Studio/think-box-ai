"""Bridge to run job status schema (PR #183 F19)."""

from __future__ import annotations

from typing import Any


def run_job_bridge_summary() -> dict[str, Any]:
    # Import lazily to avoid pulling FastAPI stack in minimal contexts.
    from backend.api.v1.run_job_status import STATUS_SCHEMA_VERSION

    return {
        "status_schema_version": STATUS_SCHEMA_VERSION,
        "surface": "backend/api/v1/run_job_status",
        "hermetic": True,
        "live_api_called": False,
    }
