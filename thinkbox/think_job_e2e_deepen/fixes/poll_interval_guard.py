"""FIX06: Guard minimum poll interval for status clients."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_stream import MIN_STREAM_POLL_INTERVAL_S


def clamp_poll_interval(seconds: float) -> float:
    return max(MIN_STREAM_POLL_INTERVAL_S, seconds)


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX06",
        "min_interval_s": MIN_STREAM_POLL_INTERVAL_S,
        "clamped": clamp_poll_interval(0.001),
        "live_api_called": False,
    }
