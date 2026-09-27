"""Worker heartbeat contract (PR #197) — deterministic, not distributed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class HeartbeatStatus(str, Enum):
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    MISSING = "MISSING"
    TIMED_OUT = "TIMED_OUT"


@dataclass
class WorkerHeartbeat:
    worker_id: str
    last_beat_at: str
    interval_s: float
    timeout_s: float

    def status(self, now: datetime | None = None) -> HeartbeatStatus:
        if not self.last_beat_at:
            return HeartbeatStatus.MISSING
        ref = now or datetime.now(timezone.utc)
        try:
            last = datetime.fromisoformat(self.last_beat_at)
        except ValueError:
            return HeartbeatStatus.MISSING
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (ref - last).total_seconds()
        if elapsed > self.timeout_s:
            return HeartbeatStatus.TIMED_OUT
        if elapsed > self.interval_s * 2:
            return HeartbeatStatus.STALE
        return HeartbeatStatus.ACTIVE

    def snapshot(self) -> dict[str, str | float]:
        return {
            "worker_id": self.worker_id,
            "last_beat_at": self.last_beat_at,
            "interval_s": self.interval_s,
            "timeout_s": self.timeout_s,
            "status": self.status().value,
        }
