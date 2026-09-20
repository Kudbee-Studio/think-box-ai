"""Process-local writer serialization for org-memory append paths."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Iterator

from thinkbox.org_memory_receipts import OrgMemoryReceipt, OrgMemoryReceiptStore

_store_write_lock = threading.RLock()


@contextmanager
def serialized_org_memory_write() -> Iterator[None]:
    """Serialize concurrent pipeline control-plane writers within one process."""
    _store_write_lock.acquire()
    try:
        yield
    finally:
        _store_write_lock.release()


def append_pipeline_lifecycle(store: OrgMemoryReceiptStore, **kwargs: Any) -> OrgMemoryReceipt:
    """Append one lifecycle receipt under the pipeline writer lock."""
    with serialized_org_memory_write():
        return store.append_lifecycle(**kwargs)
