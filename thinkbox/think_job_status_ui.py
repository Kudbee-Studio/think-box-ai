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


def api_headers(api_key: str, *, bearer: str = "") -> dict[str, str]:
    """Fail-closed auth: require API key or bearer."""
    headers: dict[str, str] = {"Accept": "application/json"}
    key = (api_key or "").strip()
    tok = (bearer or "").strip()
    if key:
        headers["X-API-Key"] = key
    elif tok:
        headers["Authorization"] = tok if tok.lower().startswith("bearer ") else f"Bearer {tok}"
    else:
        raise ValueError("api_key_or_bearer_required")
    return headers


def format_job_poll_path(engine_id: str) -> str:
    return f"/api/v1/run/job/{engine_id}/status"


def format_receipt_poll_path(receipt_id: str) -> str:
    return f"/api/v1/run/job/by-receipt/{receipt_id}/status"


def format_jobs_digest_poll_path() -> str:
    return "/api/v1/run/jobs/status/digest"


def format_jobs_list_poll_path(limit: int = 50, detail: str = "summary") -> str:
    return f"/api/v1/run/jobs/status?limit={max(1, min(limit, 200))}&detail={detail}"


def format_job_stream_path(engine_id: str) -> str:
    return f"/api/v1/run/job/{engine_id}/status/stream"


def format_receipt_stream_path(receipt_id: str) -> str:
    return f"/api/v1/run/job/by-receipt/{receipt_id}/status/stream"


def format_jobs_digest_stream_path() -> str:
    return "/api/v1/run/jobs/status/stream"


def build_stream_url(
    path: str,
    query: Mapping[str, str] | None = None,
) -> str:
    params = dict(DEFAULT_STREAM_QUERY)
    if query:
        params.update({k: str(v) for k, v in query.items()})
    return f"{path}?{urlencode(params)}"


def normalize_receipt_key(raw: str) -> str:
    """Fail-closed receipt id for watch start."""
    key = (raw or "").strip()
    if not key:
        raise ValueError("receipt_key_required")
    if len(key) > RECEIPT_KEY_MAX_LEN:
        raise ValueError("receipt_key_too_long")
    lowered = key.lower()
    for bad in INVALID_RECEIPT_PREFIXES:
        if lowered.startswith(bad):
            raise ValueError("receipt_key_invalid")
    return key


def normalize_engine_key(raw: str) -> str:
    key = (raw or "").strip()
    if not key:
        raise ValueError("engine_key_required")
    if len(key) > RECEIPT_KEY_MAX_LEN:
        raise ValueError("engine_key_too_long")
    return key


def resolve_watch_target(
    *,
    engine_id: str = "",
    receipt_id: str = "",
    prefer_receipt: bool = True,
) -> WatchTarget:
    """Choose watch key: receipt wins when both provided (founder #139)."""
    eng = (engine_id or "").strip()
    rec = (receipt_id or "").strip()
    if rec and prefer_receipt:
        return WatchTarget(kind=WatchKeyKind.RECEIPT, key=normalize_receipt_key(rec))
    if eng:
        return WatchTarget(kind=WatchKeyKind.ENGINE, key=normalize_engine_key(eng))
    if rec:
        return WatchTarget(kind=WatchKeyKind.RECEIPT, key=normalize_receipt_key(rec))
    raise ValueError("watch_target_required")


def poll_path_for_target(target: WatchTarget) -> str:
    if target.kind == WatchKeyKind.RECEIPT:
        return format_receipt_poll_path(target.key)
    return format_job_poll_path(target.key)


def assert_receipt_watch_consistency(target: WatchTarget, poll_document: Mapping[str, Any]) -> None:
    """Fail-closed when poll document does not match receipt-keyed watch."""
    if target.kind != WatchKeyKind.RECEIPT:
        return
    receipt = poll_document.get("receipt") if isinstance(poll_document.get("receipt"), dict) else {}
    rid = str(receipt.get("receipt_id") or "")
    if not rid:
        raise ValueError("receipt_not_linked")
    if rid != target.key:
        raise ValueError("receipt_key_mismatch")


def stream_plan_for_watch_target(
    target: WatchTarget,
    poll_document: Mapping[str, Any],
) -> StreamEndpointPlan:
    """Receipt-keyed stream URL when poll hints include receipt_path."""
