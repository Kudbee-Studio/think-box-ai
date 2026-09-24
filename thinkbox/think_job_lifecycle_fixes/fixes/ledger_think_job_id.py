"""FIX12: Ledger metadata includes think_job_id."""
from __future__ import annotations
from typing import Any

def ledger_metadata(think_job_id: str) -> dict[str, Any]:
    return {"think_job_id": think_job_id}

def apply_fix() -> dict[str, Any]:
    meta = ledger_metadata("tb_job_1")
    return {"fix_id": "FIX12", "has_key": "think_job_id" in meta, "live_api_called": False}
