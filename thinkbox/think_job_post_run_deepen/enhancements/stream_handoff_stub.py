"""Handoff from POST /run to stream subscription."""

from __future__ import annotations

from typing import Any


def stream_handoff(job_id: str) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "stream_path": f"/api/v1/run/{job_id}/stream",
        "hermetic": True,
        "live_api_called": False,
    }
