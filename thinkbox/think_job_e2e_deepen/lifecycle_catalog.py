"""Hermetic lifecycle transitions aligned with e2e F023 (PR #183 F07)."""

from __future__ import annotations

from typing import Any

_VALID: dict[str, tuple[str, ...]] = {
    "PENDING": ("CONFIGURED", "CANCELLED"),
    "CONFIGURED": ("RUNNING", "CANCELLED"),
    "RUNNING": ("COMPLETE", "FAILED", "CANCELLED"),
}


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in _VALID.get(from_state, ())


def transition_stub(from_state: str, to_state: str) -> dict[str, Any]:
    ok = can_transition(from_state, to_state)
    return {
        "from": from_state,
        "to": to_state,
        "allowed": ok,
        "live_api_called": False,
    }
