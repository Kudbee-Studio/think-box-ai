"""Snapshot hashing for provider call deduplication."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def snapshot_hash(messages: list[Any], **kwargs: Any) -> str:
    """Deterministic hash of model input for cache/dedup."""
    payload = json.dumps(
        {"messages": messages, "kwargs": kwargs},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
