"""Receipt handoff after POST /run."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_post_run_deepen.receipt_stub import emit_run_receipt


def receipt_handoff(job_id: str, receipt_id: str) -> dict[str, Any]:
    emitted = emit_run_receipt(job_id, receipt_id)
    return {**emitted, "handoff": True, "live_api_called": False}
