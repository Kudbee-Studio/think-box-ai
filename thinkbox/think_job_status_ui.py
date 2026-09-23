"""Control-plane Think Job status client helpers (PR #138, #139).

Hermetic subscribe + poll fallback logic shared by browser JS and unit tests.
PR #139 adds receipt-keyed watch targets and jobs-digest multiplex panel state.
Does not perform HTTP — callers supply fetch/EventSource.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

DEFAULT_STREAM_QUERY = {
    "max_events": "32",
    "timeout_s": "120",
    "heartbeat_s": "15",
}

MIN_BACKOFF_MS = 500
MAX_BACKOFF_MS = 30_000
BACKOFF_FACTOR = 1.8


class TransportMode(str, Enum):
    """How the UI receives job status updates."""

    IDLE = "idle"
    SSE = "sse"
    POLL = "poll"
    DEGRADED_POLL = "degraded_poll"


class WatchKeyKind(str, Enum):
    """Whether the UI watch session is keyed by engine id or receipt id."""

    ENGINE = "engine"
    RECEIPT = "receipt"


RECEIPT_KEY_MAX_LEN = 256
INVALID_RECEIPT_PREFIXES = ("receipt_missing",)

