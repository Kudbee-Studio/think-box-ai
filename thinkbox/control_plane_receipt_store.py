"""Process-local ActionReceiptStore for control-plane HTTP (PR #155, hermetic)."""

from __future__ import annotations

import threading

from thinkbox.agent.control_plane.store import ActionReceiptStore

_store: ActionReceiptStore | None = None
_lock = threading.Lock()


def get_control_plane_receipt_store() -> ActionReceiptStore:
    """Shared in-memory chain for control-plane routes (hermetic default)."""
    global _store
    with _lock:
        if _store is None:
            _store = ActionReceiptStore(":memory:")
        return _store


def reset_control_plane_receipt_store() -> None:
    """Test isolation."""
    global _store
    with _lock:
        if _store is not None:
            _store.close()
        _store = None
