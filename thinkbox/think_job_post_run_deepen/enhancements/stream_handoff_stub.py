"""Handoff from POST /run to stream subscription."""

from __future__ import annotations

from typing import Any


def stream_handoff(job_id: str = "tb_job_hermetic") -> dict[str, Any]:
    from thinkbox.think_job_stream import STREAM_SCHEMA_VERSION

    return {
        "job_id": job_id,
        "stream_path": f"/api/v1/run/{job_id}/stream",
        "stream_schema_version": STREAM_SCHEMA_VERSION,
        "hermetic": True,
        "live_api_called": False,
    }
