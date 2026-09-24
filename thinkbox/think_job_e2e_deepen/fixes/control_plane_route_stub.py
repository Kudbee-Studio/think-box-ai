"""FIX19: Hermetic control-plane Think Job route catalog stub."""

from __future__ import annotations

from typing import Any


def control_plane_routes() -> list[dict[str, str]]:
    return [
        {"path": "/api/v1/run/{job_id}/status", "hermetic": "true"},
        {"path": "/api/v1/run/{job_id}/stream", "hermetic": "true"},
    ]


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX19",
        "routes": control_plane_routes(),
        "live_api_called": False,
    }
