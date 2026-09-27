"""Bridge to think_job_status_ui watch helpers (PR #183 F18)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_status_ui import normalize_receipt_key, normalize_engine_key


def status_ui_bridge_summary() -> dict[str, Any]:
    return {
        "receipt_key_example": normalize_receipt_key(" receipt-demo "),
        "engine_key_example": normalize_engine_key("engine-demo"),
        "surface": "think_job_status_ui",
        "hermetic": True,
        "live_api_called": False,
    }
