"""FIX07: Hermetic jobs digest delta stub (multiplex panel)."""

from __future__ import annotations

from typing import Any


def jobs_digest_delta_stub(job_ids: list[str]) -> dict[str, Any]:
    return {
        "kind": "think_jobs_digest_delta",
        "jobs": [{"job_id": jid, "state": "RUNNING"} for jid in job_ids[:8]],
        "live_api_called": False,
    }


def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX07", **jobs_digest_delta_stub(["tb_job_a", "tb_job_b"])}
