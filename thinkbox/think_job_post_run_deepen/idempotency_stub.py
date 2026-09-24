"""Idempotency key stub for POST /run (hermetic)."""

from __future__ import annotations

from typing import Any


def idempotency_key(goal: str, agent_id: str) -> str:
    return f"idempotency:{agent_id}:{hash(goal) & 0xFFFFFFFF:08x}"


def apply_idempotency(goal: str, agent_id: str, seen: set[str] | None = None) -> dict[str, Any]:
    store = seen if seen is not None else set()
    key = idempotency_key(goal, agent_id)
    duplicate = key in store
    if not duplicate:
        store.add(key)
    return {"key": key, "duplicate": duplicate, "live_api_called": False}
