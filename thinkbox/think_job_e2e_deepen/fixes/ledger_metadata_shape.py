"""FIX14: Ledger metadata shape for Think Job attempts."""

from __future__ import annotations

from typing import Any


def ledger_metadata_shape(job_id: str, attempt: int) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "attempt": attempt,
        "think_job_e2e": True,
        "live_api_called": False,
    }


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX14",
        "metadata": ledger_metadata_shape("tb_job_x", 1),
        "live_api_called": False,
    }
