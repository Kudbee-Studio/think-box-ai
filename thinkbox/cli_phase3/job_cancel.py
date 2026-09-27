"""Hermetic job cancel mirror (PR #180 F10)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobCancelResult:
    job_id: str
    cancelled: bool
    reason: str | None


def cancel_job_hermetic(job_id: str) -> JobCancelResult:
    if not job_id.startswith("tb_job_"):
        return JobCancelResult(job_id=job_id, cancelled=False, reason="invalid_job_id")
    if job_id.endswith("_terminal"):
        return JobCancelResult(job_id=job_id, cancelled=False, reason="already_terminal")
    return JobCancelResult(job_id=job_id, cancelled=True, reason=None)
