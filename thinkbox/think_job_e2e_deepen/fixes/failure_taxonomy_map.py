"""FIX12: Map job failures to retry taxonomies."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_e2e_deepen.retry import should_retry_step

_TAXONOMY: dict[str, str] = {
    "timeout": "transient",
    "wrong_key": "distractor-compliance",
    "budget": "non_retryable",
}


def apply_fix() -> dict[str, Any]:
    mapped = {
        code: should_retry_step(tax, 1).should_retry
        for code, tax in _TAXONOMY.items()
    }
    return {"fix_id": "FIX12", "retry_map": mapped, "live_api_called": False}
