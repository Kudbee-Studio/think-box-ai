"""Hermetic job status mirror (PR #180 F09)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    status: str
    progress: float
    detail: dict[str, Any]


def job_status_hermetic(job_id: str) -> JobStatus:
    if not job_id.startswith("tb_job_"):
        status = "UNKNOWN"
        progress = 0.0
    elif job_id.endswith("_fail"):
        status = "FAILED"
        progress = 1.0
    else:
        status = "SUCCEEDED"
        progress = 1.0
    return JobStatus(
        job_id=job_id,
        status=status,
        progress=progress,
        detail={"live_api_called": False, "source": "cli_phase3_mirror"},
    )
