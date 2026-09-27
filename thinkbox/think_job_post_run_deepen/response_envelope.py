"""Success envelope shape for POST /run responses (PR #184 deepen)."""

from __future__ import annotations

from typing import Any


def success_envelope(job_id: str, receipt_id: str, status: str = "started") -> dict[str, Any]:
    return {
        "ok": True,
        "job_id": job_id,
        "receipt_id": receipt_id,
        "status": status,
        "live_api_called": False,
        "evidence_label": "simulated",
    }
