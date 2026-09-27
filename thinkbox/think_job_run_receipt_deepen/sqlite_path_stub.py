"""SQLite path resolution (PR #186 F07)."""
from __future__ import annotations
from thinkbox.think_job_run_receipt_deepen.config import http_run_db_path

def resolve_db() -> dict[str, str]:
    return {"path": http_run_db_path()}
