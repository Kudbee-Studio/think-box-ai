"""Redacted local env matrix for Think Job spine (no secrets)."""

from __future__ import annotations

import os
from typing import Any

_KEYS = (
    "THINKBOX_TRACE_DB_PATH",
    "THINKBOX_CLI_DB_DIR",
    "THINKBOX_IDENTITY_LEDGER_PATH",
    "UPSTASH_PUBLIC_BOX_URL",
)


def redacted_env_matrix() -> dict[str, Any]:
    flags = {key: bool(os.environ.get(key, "").strip()) for key in _KEYS}
    return {
        "step": "env_matrix",
        "ok": True,
        "configured": flags,
        "live_api_called": False,
    }
