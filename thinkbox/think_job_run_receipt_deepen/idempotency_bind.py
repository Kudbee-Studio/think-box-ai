"""Idempotency key bind (PR #186 F12)."""
from __future__ import annotations

def idempotency_key(headers: dict[str, str]) -> str | None:
    return headers.get("Idempotency-Key") or headers.get("idempotency-key")
