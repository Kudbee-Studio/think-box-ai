"""FIX18: Stream hub test reset honesty."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_stream import get_think_job_stream_hub, reset_think_job_stream_hub_for_tests


def apply_fix() -> dict[str, Any]:
    hub = get_think_job_stream_hub()
    before = hub.generation()
    reset_think_job_stream_hub_for_tests()
    after = get_think_job_stream_hub().generation()
    return {
        "fix_id": "FIX18",
        "generation_before": before,
        "generation_after": after,
        "reset_ok": after >= before,
        "live_api_called": False,
    }
