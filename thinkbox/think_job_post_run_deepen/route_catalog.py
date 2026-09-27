"""Route catalog for POST /run control plane."""

from __future__ import annotations

from typing import Any


def post_run_routes() -> list[dict[str, str]]:
    return [
        {"method": "POST", "path": "/api/v1/run", "hermetic": "true"},
        {"method": "GET", "path": "/api/v1/run/{job_id}/status", "hermetic": "true"},
        {"method": "GET", "path": "/api/v1/run/{job_id}/stream", "hermetic": "true"},
    ]


def route_catalog_summary() -> dict[str, Any]:
    return {"routes": post_run_routes(), "live_api_called": False}
