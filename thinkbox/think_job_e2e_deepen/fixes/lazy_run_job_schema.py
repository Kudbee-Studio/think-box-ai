"""FIX01: Resolve run job status schema without eager FastAPI imports."""

from __future__ import annotations

from typing import Any

_FALLBACK_SCHEMA = "think_job_status_v1"


def resolve_status_schema_version() -> str:
    try:
        from backend.api.v1.run_job_status import STATUS_SCHEMA_VERSION

        return str(STATUS_SCHEMA_VERSION)
    except ImportError:
        return _FALLBACK_SCHEMA


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX01",
        "status_schema_version": resolve_status_schema_version(),
        "live_api_called": False,
    }
