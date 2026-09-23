"""Control-plane Think Job status client helpers (PR #138).

Hermetic subscribe + poll fallback logic shared by browser JS and unit tests.
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


def stream_url_from_poll_payload(poll_document: Mapping[str, Any]) -> StreamEndpointPlan:
    """Use poll.stream hints from #134/#137 — no parallel status plane."""
    poll = poll_document.get("poll") if isinstance(poll_document.get("poll"), dict) else {}
    stream = poll.get("stream") if isinstance(poll.get("stream"), dict) else {}
    engine_id = str(poll_document.get("engine_id") or poll_document.get("job_id") or "")
    job_template = str(stream.get("job_path") or format_job_stream_path("{engine_id}"))
    stream_path = job_template.replace("{engine_id}", engine_id)
    receipt = poll_document.get("receipt") if isinstance(poll_document.get("receipt"), dict) else {}
    receipt_id = str(receipt.get("receipt_id") or "")
    receipt_template = str(stream.get("receipt_path") or "")
    receipt_stream = (
        receipt_template.replace("{receipt_id}", receipt_id) if receipt_id and receipt_template else None
    )
    interval = int(poll.get("recommended_interval_ms") or 5000)
    return StreamEndpointPlan(
        poll_url=format_job_poll_path(engine_id),
        stream_url=build_stream_url(stream_path),
        receipt_stream_url=build_stream_url(receipt_stream) if receipt_stream else None,
        recommended_interval_ms=max(500, interval),
    )


def append_query_api_key(url: str, api_key: str) -> str:
    """Optional EventSource auth when THINKBOX_ALLOW_QUERY_API_KEY is enabled."""
    key = (api_key or "").strip()
    if not key:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}api_key={key}"


def parse_sse_buffer_incremental(
    buffer: str,
) -> tuple[list[dict[str, Any]], str]:
    """Split complete SSE blocks from buffer; return remainder."""
    events: list[dict[str, Any]] = []
    parts = buffer.split("\n\n")
    rest = parts.pop() if parts else ""
    for block in parts:
        if not block.strip():
            continue
        data_line = next((ln for ln in block.splitlines() if ln.startswith("data: ")), "")
        if not data_line:
            continue
        try:
            events.append(json.loads(data_line[6:]))
        except json.JSONDecodeError as exc:
            events.append({"kind": "parse_error", "error": str(exc)})
    return events, rest


def parse_sse_data_events(raw: str) -> list[dict[str, Any]]:
    """Parse SSE blocks into JSON data payloads (hermetic tests + JS parity)."""
    events: list[dict[str, Any]] = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        data_line = next((ln for ln in block.splitlines() if ln.startswith("data: ")), "")
        if not data_line:
            continue
        try:
            events.append(json.loads(data_line[6:]))
        except json.JSONDecodeError as exc:
            events.append({"kind": "parse_error", "error": str(exc), "raw": data_line[6:][:200]})
    return events


def apply_status_event(
    state: ThinkJobWatchState,
    event: Mapping[str, Any],
) -> bool:
    """Merge hello/delta/close into watch state; return True if summary changed."""
    kind = str(event.get("kind") or "")
    state.telemetry.events_received += 1
    if kind == "think_job_stream_hello":
        snap = event.get("snapshot")
        if isinstance(snap, dict):
            state.summary = dict(snap)
            state.last_sequence = int(event.get("sequence") or 0)
            return True
    if kind == "think_job_status_delta":
        seq = int(event.get("sequence") or 0)
        if seq >= state.last_sequence:
            state.last_sequence = seq
        merged = dict(state.summary or {})
        for key in (
            "status",
            "phase",
            "progress",
            "job_id",
            "engine_id",
            "receipt",
            "tasks_total",
            "tasks_completed",
            "poll",
            "four_state",
        ):
            if key in event:
                merged[key] = event[key]
        state.summary = merged
        return True
    if kind == "think_job_stream_close":
        reason = str(event.get("reason") or "closed")
        state.telemetry.last_error = f"stream_close:{reason}"
        return False
    if kind == "think_job_stream_heartbeat":
        return False
    if kind == "parse_error":
        state.telemetry.last_error = str(event.get("error") or "sse_parse_error")
        state.telemetry.poll_error_count += 1
        return False
    return False


def backoff_delay_ms(attempt: int, *, base_ms: int = MIN_BACKOFF_MS) -> int:
    """Exponential backoff with cap for SSE reconnect."""
    attempt = max(0, attempt)
    delay = base_ms * (BACKOFF_FACTOR ** attempt)
    return int(min(MAX_BACKOFF_MS, math.ceil(delay)))


def should_enter_poll_fallback(
    *,
    sse_supported: bool,
    sse_failed: bool,
    stream_available: bool,
) -> bool:
    if not stream_available:
        return True
    if not sse_supported:
        return True
    return sse_failed


def classify_transport_after_error(
    current: TransportMode,
    *,
    sse_recoverable: bool,
) -> TransportMode:
    if current == TransportMode.SSE and not sse_recoverable:
        return TransportMode.DEGRADED_POLL
    if current == TransportMode.SSE:
        return TransportMode.POLL
    return TransportMode.DEGRADED_POLL


def terminal_from_summary(summary: Mapping[str, Any] | None) -> bool:
    if not summary:
        return False
    poll = summary.get("poll") if isinstance(summary.get("poll"), dict) else {}
    if poll.get("terminal") is True:
        return True
    status = str(summary.get("status") or "").lower()
    return status in {"completed", "failed", "cancelled", "error"}


def digest_row_label(row: Mapping[str, Any]) -> str:
    jid = str(row.get("job_id") or row.get("engine_id") or "?")
    status = str(row.get("status") or "?")
    return f"{jid} ({status})"


def select_jobs_from_digest(digest: Mapping[str, Any], limit: int = 50) -> Sequence[dict[str, Any]]:
    jobs = digest.get("jobs")
    if not isinstance(jobs, list):
        return []
    out: list[dict[str, Any]] = []
    for item in jobs[: max(1, min(limit, 200))]:
        if isinstance(item, dict):
            out.append(item)
    return out


__all__ = [
    "TransportMode",
    "StreamEndpointPlan",
    "ThinkJobClientTelemetry",
    "ThinkJobWatchState",
    "api_headers",
    "format_job_poll_path",
    "format_job_stream_path",
    "format_receipt_stream_path",
    "format_jobs_digest_stream_path",
    "build_stream_url",
    "stream_url_from_poll_payload",
    "append_query_api_key",
    "parse_sse_buffer_incremental",
    "parse_sse_data_events",
    "apply_status_event",
    "backoff_delay_ms",
    "should_enter_poll_fallback",
    "classify_transport_after_error",
    "terminal_from_summary",
    "digest_row_label",
    "select_jobs_from_digest",
]
