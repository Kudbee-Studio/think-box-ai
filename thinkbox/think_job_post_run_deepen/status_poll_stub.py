"""Started-status poll stub (PR #184 F16)."""
from __future__ import annotations
from typing import Any

def started_status(job_id: str) -> dict[str, Any]:
    return {"job_id": job_id, "status": "started", "live_api_called": False}


def status_poll_hint() -> dict[str, Any]:
    from thinkbox.think_job_stream import MIN_STREAM_POLL_INTERVAL_S

    return {
        "interval_s": MIN_STREAM_POLL_INTERVAL_S,
        "min_interval_s": MIN_STREAM_POLL_INTERVAL_S,
        "live_api_called": False,
    }
