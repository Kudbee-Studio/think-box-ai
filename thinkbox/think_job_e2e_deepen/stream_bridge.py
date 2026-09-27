"""Bridge to think_job_stream hermetic SSE (PR #183 F17)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_stream import STREAM_SCHEMA_VERSION, ThinkJobStreamLimits


def stream_bridge_summary() -> dict[str, Any]:
    limits = ThinkJobStreamLimits()
    return {
        "stream_schema_version": STREAM_SCHEMA_VERSION,
        "max_events": limits.max_events,
        "max_frame_bytes": limits.max_frame_bytes,
        "hermetic": True,
        "live_api_called": False,
        "deepen_layer": "pr183-think-job-hermetic-e2e",
    }
