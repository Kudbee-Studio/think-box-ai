"""Fail-closed config (PR #186 F04)."""
from __future__ import annotations
import os

def http_run_db_path() -> str:
    return os.environ.get("THINKBOX_HTTP_RUN_DB", "data/thinkboxmd/db/http_run_experiments.db")
