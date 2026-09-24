"""Structured errors for lifecycle fix pack (PR #185)."""

from __future__ import annotations

from typing import Any


def structured_error(error_type: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "error_type": error_type,
        "context": context,
        "live_api_called": False,
    }
