"""Bridge to run_job_status (PR #186 F13)."""
from __future__ import annotations

def bridge_job_id(receipt: dict[str, object]) -> str | None:
    return str(receipt.get("engine_id") or receipt.get("job_id") or "") or None
