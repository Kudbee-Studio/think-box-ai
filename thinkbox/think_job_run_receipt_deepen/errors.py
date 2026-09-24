"""Structured errors (PR #186 F02)."""
from __future__ import annotations
from typing import Any

def receipt_error(code: str, context: dict[str, Any]) -> dict[str, Any]:
    return {"error_type": code, "context": context, "live_api_called": False}
