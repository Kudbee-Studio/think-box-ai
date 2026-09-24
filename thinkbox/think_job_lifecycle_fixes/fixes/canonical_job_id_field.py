"""FIX03: Canonical job id field for reports."""
from __future__ import annotations
from typing import Any

def normalize_job_record(record: dict[str, Any]) -> dict[str, Any]:
    job_id = record.get("job_id") or record.get("engine_id")
    return {"job_id": job_id, "engine_id": job_id}

def apply_fix() -> dict[str, Any]:
    out = normalize_job_record({"engine_id": "tb_job_x"})
    return {"fix_id": "FIX03", "canonical": out["job_id"] == "tb_job_x", "live_api_called": False}
