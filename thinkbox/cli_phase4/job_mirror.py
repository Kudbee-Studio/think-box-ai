"""Hermetic job create mirror (PR #196 F08)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobCreateResult:
    job_id: str
    status: str
    payload_sha256: str


def create_job_hermetic(goal: str, metadata: dict[str, Any] | None = None) -> JobCreateResult:
    meta = metadata or {}
    body = {"goal": goal, "metadata": meta}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    job_id = f"tb_job_cli3_{digest[:12]}"
    return JobCreateResult(job_id=job_id, status="QUEUED", payload_sha256=digest)
