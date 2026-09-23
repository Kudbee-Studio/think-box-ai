"""Hermetic SSE endpoints for Think Job status deltas (PR #137)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, AsyncGenerator

from backend.validation import MAX_STREAM_EVENTS, MAX_STREAM_TIMEOUT_S, clamp_stream_scalar

from thinkbox.dashboard_state import get_dashboard_state
from thinkbox.think_job_stream import (
    ThinkJobStreamLimits,
    build_stream_heartbeat,
    build_stream_hello,
    build_stream_terminal,
    compute_status_delta,
    format_sse_data,
    get_think_job_stream_hub,
    new_stream_id,
    status_fingerprint,
    STREAM_SCHEMA_VERSION,
)

from backend.api.v1.run_job_status import (
    TERMINAL_STATUSES,
    ThinkJobNotFoundError,
    build_think_job_status_summary,
    resolve_think_job_by_receipt,
    resolve_think_job_record,
)

__all__ = [
    "STREAM_SCHEMA_VERSION",
    "ThinkJobStreamLimits",
    "clamp_stream_query_params",
    "iter_jobs_status_stream",
    "iter_think_job_status_stream",
]


def clamp_stream_query_params(
    max_events: int,
    timeout_s: float,
    heartbeat_s: float,
) -> ThinkJobStreamLimits:
    limits = ThinkJobStreamLimits()
    env_cap = int(os.environ.get("THINKBOX_STREAM_MAX_EVENTS", str(limits.max_events)))
    cap = max(1, min(env_cap, MAX_STREAM_EVENTS))
    max_events = int(clamp_stream_scalar(max_events, default=cap, minimum=1, maximum=cap))
    timeout_s = clamp_stream_scalar(
        timeout_s,
        default=limits.idle_timeout_s,
        minimum=1.0,
        maximum=min(limits.idle_timeout_s, MAX_STREAM_TIMEOUT_S),
    )
    heartbeat_s = clamp_stream_scalar(
        heartbeat_s,
        default=limits.heartbeat_interval_s,
        minimum=1.0,
        maximum=limits.heartbeat_interval_s,
    )
    return ThinkJobStreamLimits(
        max_events=max_events,
        max_frame_bytes=limits.max_frame_bytes,
        heartbeat_interval_s=heartbeat_s,
        idle_timeout_s=timeout_s,
        poll_interval_s=limits.poll_interval_s,
    )


def _summary_for_record(record: dict[str, Any]) -> dict[str, Any]:
    return build_think_job_status_summary(record)


async def iter_think_job_status_stream(
    job_id: str,
    *,
    limits: ThinkJobStreamLimits | None = None,
    include_hello: bool = True,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames until terminal status, max_events, or idle timeout."""
    limits = limits or ThinkJobStreamLimits()
    hub = get_think_job_stream_hub()
    dashboard = get_dashboard_state()
    stream_id = new_stream_id()
    sequence = 0
    previous: dict[str, Any] | None = None
    started = time.monotonic()
    last_emit = started
    events_sent = 0

    record = resolve_think_job_record(job_id)
    job_key = str(record.get("job_id") or record.get("engine_id") or job_id)

    if include_hello:
        summary = _summary_for_record(record)
        hello = build_stream_hello(summary, stream_id=stream_id, job_id=job_key)
        yield format_sse_data(hello, event="hello")
        events_sent += 1
        previous = summary
        sequence += 1
        if str(summary.get("status") or "") in TERMINAL_STATUSES:
            close = build_stream_terminal(
                stream_id=stream_id,
                job_id=job_key,
                sequence=sequence,
                reason="terminal",
            )
            yield format_sse_data(close, event="close")
            return

    last_gen = hub.job_generation(job_key)
    last_rev = dashboard.revision()

    while events_sent < limits.max_events:
        if time.monotonic() - started > limits.idle_timeout_s:
            close = build_stream_terminal(
                stream_id=stream_id,
                job_id=job_key,
                sequence=sequence,
                reason="idle_timeout",
            )
            yield format_sse_data(close, event="close")
            return

        record = resolve_think_job_record(job_key)
        summary = _summary_for_record(record)
        fp = status_fingerprint(summary)
        prev_fp = status_fingerprint(previous) if previous else ""

        if fp != prev_fp:
            delta = compute_status_delta(previous, summary, sequence=sequence)
            yield format_sse_data(delta, event="status")
            events_sent += 1
            sequence += 1
            previous = summary
            last_emit = time.monotonic()
            if str(summary.get("status") or "") in TERMINAL_STATUSES:
                close = build_stream_terminal(
                    stream_id=stream_id,
                    job_id=job_key,
                    sequence=sequence,
                    reason="terminal",
                )
                yield format_sse_data(close, event="close")
                return

        now = time.monotonic()
        if now - last_emit >= limits.heartbeat_interval_s:
            hb = build_stream_heartbeat(
                stream_id=stream_id,
                job_id=job_key,
                sequence=sequence,
                dashboard_revision=dashboard.revision(),
            )
            yield format_sse_data(hb, event="heartbeat")
            events_sent += 1
            last_emit = now

        gen = hub.job_generation(job_key)
        rev = dashboard.revision()
        if gen == last_gen and rev == last_rev:
            try:
                await asyncio.wait_for(
                    _wait_for_job_wake(hub, job_key, last_gen, last_rev),
                    timeout=limits.poll_interval_s,
                )
            except asyncio.TimeoutError:
                pass
        last_gen = hub.job_generation(job_key)
        last_rev = dashboard.revision()


async def _wait_for_job_wake(
    hub: Any,
    job_id: str,
    last_job_gen: int,
    last_rev: int,
) -> None:
    """Block until hub or dashboard revision advances."""
    dashboard = get_dashboard_state()
    while True:
        if hub.job_generation(job_id) != last_job_gen:
            return
        if dashboard.revision() != last_rev:
            return
        await asyncio.sleep(limits_poll_interval())


def limits_poll_interval() -> float:
    return ThinkJobStreamLimits().poll_interval_s



