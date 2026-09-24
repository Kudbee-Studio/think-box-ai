"""FIX05: Artifact dir has sane default."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.artifact_path_stub import artifact_dir
    d = artifact_dir()
    return {"fix_id": "FIX05", "ok": "http_run" in d, "live_api_called": False}
