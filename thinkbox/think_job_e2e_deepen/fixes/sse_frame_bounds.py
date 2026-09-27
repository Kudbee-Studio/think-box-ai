"""FIX05: Enforce SSE frame bounds from think_job_stream."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_stream import MAX_SSE_FRAME_BYTES, ThinkJobStreamLimits


def apply_fix() -> dict[str, Any]:
    limits = ThinkJobStreamLimits()
    return {
        "fix_id": "FIX05",
        "max_frame_bytes": min(limits.max_frame_bytes, MAX_SSE_FRAME_BYTES),
        "within_bounds": limits.max_frame_bytes <= MAX_SSE_FRAME_BYTES,
        "live_api_called": False,
    }
