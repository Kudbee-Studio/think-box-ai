"""Stream receipt link (PR #186 F15)."""
from __future__ import annotations
from typing import Any

def stream_path(job_id: str) -> dict[str, Any]:
    return {"path": f"/api/v1/run/{job_id}/stream", "live_api_called": False}
