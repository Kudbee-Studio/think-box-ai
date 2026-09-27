"""Hermetic Think Job status delta + SSE helpers (PR #137).

Poll → push: clients subscribe to incremental status updates without live Mercury.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from thinkbox.org_memory_receipts import redact_mapping

STREAM_SCHEMA_VERSION = "think_job_status_stream_v1"
MAX_SSE_FRAME_BYTES = 16_384
DEFAULT_STREAM_MAX_EVENTS = 64
DEFAULT_STREAM_HEARTBEAT_S = 15.0
DEFAULT_STREAM_IDLE_TIMEOUT_S = 120.0
MIN_STREAM_POLL_INTERVAL_S = 0.05


@dataclass(frozen=True)
class ThinkJobStreamLimits:
    """Fail-closed bounds for hermetic SSE sessions."""

    max_events: int = DEFAULT_STREAM_MAX_EVENTS
    max_frame_bytes: int = MAX_SSE_FRAME_BYTES
    heartbeat_interval_s: float = DEFAULT_STREAM_HEARTBEAT_S
    idle_timeout_s: float = DEFAULT_STREAM_IDLE_TIMEOUT_S
    poll_interval_s: float = MIN_STREAM_POLL_INTERVAL_S


@dataclass
class ThinkJobStreamHub:
    """In-process wake signals for status stream loops (hermetic / unittest-safe)."""

    _generation: int = 0
    _job_generation: dict[str, int] = field(default_factory=dict)

    def signal(self, job_id: str = "") -> None:
        self._generation += 1
        if job_id:
            self._job_generation[job_id] = self._job_generation.get(job_id, 0) + 1

    def generation(self) -> int:
        return self._generation

    def job_generation(self, job_id: str) -> int:
        return self._job_generation.get(job_id, 0)

    def reset_for_tests(self) -> None:
        self._generation = 0
        self._job_generation.clear()


_hub: ThinkJobStreamHub | None = None


def get_think_job_stream_hub() -> ThinkJobStreamHub:
    global _hub
    if _hub is None:
        _hub = ThinkJobStreamHub()
    return _hub


def reset_think_job_stream_hub_for_tests() -> None:
    get_think_job_stream_hub().reset_for_tests()


def status_fingerprint(summary: dict[str, Any]) -> str:
    """Stable hash key for deduplicating poll snapshots."""
    receipt = summary.get("receipt") if isinstance(summary.get("receipt"), dict) else {}
    parts = (
        str(summary.get("job_id") or ""),
        str(summary.get("status") or ""),
        str(summary.get("phase") or ""),
        str(summary.get("progress") or 0.0),
        str(summary.get("tasks_total") or 0),
        str(summary.get("tasks_completed") or 0),
        str(receipt.get("receipt_id") or ""),
        str(receipt.get("linked") or False),
    )
    return "|".join(parts)


def compute_status_delta(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    *,
    sequence: int,
) -> dict[str, Any]:
    """Incremental update document (summary-shaped, redacted)."""
    prev_fp = status_fingerprint(previous) if previous else ""
    curr_fp = status_fingerprint(current)
    changed_fields: list[str] = []
    if previous is None:
        changed_fields = ["initial"]
    else:
        for key in ("status", "phase", "progress", "tasks_total", "tasks_completed"):
            if previous.get(key) != current.get(key):
                changed_fields.append(key)
        prev_rcpt = previous.get("receipt") if isinstance(previous.get("receipt"), dict) else {}
        curr_rcpt = current.get("receipt") if isinstance(current.get("receipt"), dict) else {}
        if prev_rcpt != curr_rcpt:
            changed_fields.append("receipt")
    return redact_mapping(
        {
            "kind": "think_job_status_delta",
            "schema_version": STREAM_SCHEMA_VERSION,
            "sequence": sequence,
            "fingerprint": curr_fp,
            "changed": changed_fields,
            "previous_fingerprint": prev_fp,
            "status": current.get("status"),
            "phase": current.get("phase"),
            "progress": current.get("progress"),
            "job_id": current.get("job_id"),
            "engine_id": current.get("engine_id"),
            "receipt": current.get("receipt"),
            "tasks_total": current.get("tasks_total"),
            "tasks_completed": current.get("tasks_completed"),
            "poll": current.get("poll"),
            "four_state": current.get("four_state"),
            "live_verified": False,
            "production_ready": False,
        }
    )


def build_stream_hello(
    summary: dict[str, Any],
    *,
    stream_id: str,
    job_id: str,
) -> dict[str, Any]:
    return redact_mapping(
        {
            "kind": "think_job_stream_hello",
            "schema_version": STREAM_SCHEMA_VERSION,
            "stream_id": stream_id,
            "job_id": job_id,
            "snapshot": summary,
            "live_verified": False,
            "production_ready": False,
        }
    )


def build_stream_heartbeat(
    *,
    stream_id: str,
    job_id: str,
    sequence: int,
    dashboard_revision: int,
) -> dict[str, Any]:
    return {
        "kind": "think_job_stream_heartbeat",
        "schema_version": STREAM_SCHEMA_VERSION,
        "stream_id": stream_id,
        "job_id": job_id,
        "sequence": sequence,
        "dashboard_revision": dashboard_revision,
        "live_verified": False,
        "production_ready": False,
    }


def build_stream_terminal(
    *,
    stream_id: str,
    job_id: str,
    sequence: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "kind": "think_job_stream_close",
        "schema_version": STREAM_SCHEMA_VERSION,
        "stream_id": stream_id,
        "job_id": job_id,
        "sequence": sequence,
        "reason": reason,
        "live_verified": False,
        "production_ready": False,
    }


def new_stream_id() -> str:
    return f"tjs_{uuid.uuid4().hex[:16]}"


def format_sse_data(payload: dict[str, Any], *, event: str | None = None) -> str:
    """Serialize one SSE frame with byte limit (fail-closed truncation marker)."""
    raw = json.dumps(payload, separators=(",", ":"), default=str)
    if len(raw.encode("utf-8")) > MAX_SSE_FRAME_BYTES:
        payload = {
            "kind": "think_job_stream_error",
            "schema_version": STREAM_SCHEMA_VERSION,
            "error": "frame_too_large",
            "max_bytes": MAX_SSE_FRAME_BYTES,
            "live_verified": False,
            "production_ready": False,
        }
        raw = json.dumps(payload, separators=(",", ":"))
    lines = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {raw}")
    lines.append("")
    return "\n".join(lines) + "\n"


def stream_hints_for_poll() -> dict[str, Any]:
    return {
        "stream_available": True,
        "stream_schema_version": STREAM_SCHEMA_VERSION,
        "job_path": "/api/v1/run/job/{engine_id}/status/stream",
        "receipt_path": "/api/v1/run/job/by-receipt/{receipt_id}/status/stream",
        "jobs_path": "/api/v1/run/jobs/status/stream",
    }


def job_status_stream_snapshot_for_governance() -> dict[str, Any]:
    return {
        "stream_schema_version": STREAM_SCHEMA_VERSION,
        "max_frame_bytes": MAX_SSE_FRAME_BYTES,
        "default_max_events": DEFAULT_STREAM_MAX_EVENTS,
        "hub_generation": get_think_job_stream_hub().generation(),
    }
