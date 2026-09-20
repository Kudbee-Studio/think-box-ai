"""Webhook delivery replay detection (hermetic, in-memory)."""

from __future__ import annotations

import threading
from typing import Optional

_seen: set[str] = set()
_lock = threading.Lock()


def register_delivery(delivery_id: str) -> bool:
    """Return True if first time seeing delivery_id."""
    if not delivery_id:
        return True
    with _lock:
        if delivery_id in _seen:
            return False
        _seen.add(delivery_id)
        return True


def reset_replay_cache() -> None:
    with _lock:
        _seen.clear()


def is_replay(delivery_id: Optional[str]) -> bool:
    if not delivery_id:
        return False
    with _lock:
        return delivery_id in _seen
