"""Receipt field schema stub (PR #186 F05)."""
from __future__ import annotations
from typing import Any

REQUIRED = ("receipt_id", "session_id", "experiment_id")

def validate_receipt_shape(body: dict[str, Any]) -> bool:
    return all(k in body for k in REQUIRED)
