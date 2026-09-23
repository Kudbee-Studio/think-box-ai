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


@dataclass
class StreamEndpointPlan:
    """Resolved URLs for one Think Job watch session."""

    poll_url: str
    stream_url: str
    receipt_stream_url: str | None = None
    recommended_interval_ms: int = 5000


@dataclass
class ThinkJobClientTelemetry:
    """Surface errors to UI — no silent swallow."""

    last_error: str = ""
    last_error_at_ms: int = 0
    sse_disconnect_count: int = 0
    poll_error_count: int = 0
    mode: TransportMode = TransportMode.IDLE
    events_received: int = 0


@dataclass
class ThinkJobWatchState:
    """In-memory status document for one engine id."""

    engine_id: str
    summary: dict[str, Any] | None = None
    last_sequence: int = 0
    telemetry: ThinkJobClientTelemetry = field(default_factory=ThinkJobClientTelemetry)
    watch_kind: WatchKeyKind = WatchKeyKind.ENGINE
    watch_key: str = ""
    receipt_id: str = ""


@dataclass
class WatchTarget:
    """Resolved UI watch identity before the first poll."""

    kind: WatchKeyKind
    key: str


@dataclass
class MultiplexPanelState:
    """Jobs digest list multiplexed with one active receipt/engine watch."""

    digest_document: dict[str, Any] | None = None
    digest_jobs: list[dict[str, Any]] = field(default_factory=list)
    dashboard_revision: int = 0
    digest_transport: TransportMode = TransportMode.IDLE
    watch_transport: TransportMode = TransportMode.IDLE
    active_target: WatchTarget | None = None
    last_digest_error: str = ""
    last_watch_error: str = ""


