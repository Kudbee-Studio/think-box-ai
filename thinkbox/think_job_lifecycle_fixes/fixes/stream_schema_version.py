"""FIX16: Stream handoff schema version matches think_job_stream."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.enhancements.stream_handoff_stub import stream_handoff
    from thinkbox.think_job_stream import STREAM_SCHEMA_VERSION
    handoff = stream_handoff()
    return {
        "fix_id": "FIX16",
        "matches": handoff.get("stream_schema_version") == STREAM_SCHEMA_VERSION,
        "live_api_called": False,
    }
