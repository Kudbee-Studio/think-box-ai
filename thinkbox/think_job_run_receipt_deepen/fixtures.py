"""Fixtures (PR #186 F11)."""
from __future__ import annotations
from typing import Any

def sample_receipt() -> dict[str, Any]:
    return {
        "receipt_id": "rcpt_hermetic",
        "session_id": "tb_sess_hermetic",
        "experiment_id": "tb_exp_hermetic",
        "live_api_called": False,
    }
