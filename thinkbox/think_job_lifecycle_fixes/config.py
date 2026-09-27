"""Fail-closed config for lifecycle fix pack (PR #185)."""

from __future__ import annotations

import os


def experiment_db_configured() -> bool:
    path = os.environ.get("THINKBOX_TRACE_DB_PATH") or os.environ.get("THINKBOX_CLI_DB_DIR")
    return bool(path and str(path).strip())
