"""Ownership leases for durable RUNNING claims.

A lease is an ownership token (``lease_id``) plus persisted start and expiry
timestamps. Expiry is the stored ``lease_expires_at``, not a recomputed guess.
This is not a worker, scheduler, or reaper.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DEFAULT_LEASE_TIMEOUT_SECONDS = 300
TIMEOUT_REASON_EXPIRED = "lease_expired"


@dataclass(frozen=True)
class LeaseClaim:
    """One durable ownership claim."""

    lease_id: str
    started_at: str
    expires_at: str
    timeout_seconds: int


def _aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def issue_lease(
    now: datetime | None = None,
    timeout_seconds: int = DEFAULT_LEASE_TIMEOUT_SECONDS,
) -> LeaseClaim:
    """Mint an ownership lease. ``lease_id`` is not a timestamp."""
    if timeout_seconds < 0:
        raise ValueError("lease timeout must be >= 0")
    moment = _aware(now or datetime.now(timezone.utc))
    return LeaseClaim(
        lease_id=uuid.uuid4().hex,
        started_at=moment.isoformat(),
        expires_at=(moment + timedelta(seconds=timeout_seconds)).isoformat(),
        timeout_seconds=timeout_seconds,
    )


def parse_lease_timestamp(value: str) -> datetime | None:
    """Parse a persisted ISO timestamp. Unparseable values are not expired."""
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return _aware(parsed)


def lease_is_expired(expires_at: str, now: datetime) -> bool:
    """True when ``now`` is at or after the persisted expiry."""
    expiry = parse_lease_timestamp(expires_at)
    if expiry is None:
        return False
    return _aware(now) >= expiry
