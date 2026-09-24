"""Status poll receipt link (PR #186 F14)."""
from __future__ import annotations
from typing import Any

def status_path(job_id: str) -> dict[str, Any]:
    return {"path": f"/api/v1/run/job/{job_id}/status", "live_api_called": False}
