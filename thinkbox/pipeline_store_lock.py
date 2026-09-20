"""Process-local writer serialization for org-memory append paths."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

_store_write_lock = threading.RLock()


@contextmanager
def serialized_org_memory_write() -> Iterator[None]:
    """Serialize concurrent pipeline writers within one process."""
    _store_write_lock.acquire()
    try:
        yield
    finally:
        _store_write_lock.release()
