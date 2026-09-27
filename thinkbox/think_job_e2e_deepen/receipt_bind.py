"""Receipt bind stub for Think Job watch surfaces (PR #183 F13)."""

from __future__ import annotations

from typing import Any


def bind_receipt_to_job(receipt_id: str, job_id: str) -> dict[str, Any]:
    key = receipt_id.strip()
    if not key:
        return {"bound": False, "error": "empty_receipt", "live_api_called": False}
    return {
        "bound": True,
        "receipt_id": key,
        "job_id": job_id,
        "watch_token": f"watch:{key}:{job_id}",
        "live_api_called": False,
    }


def unbind_receipt_stub(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "bound": False,
        "previous_receipt_id": binding.get("receipt_id"),
        "live_api_called": False,
    }
