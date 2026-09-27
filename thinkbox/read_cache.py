"""Process-local read caches for hermetic API snapshots (PR #135).

Fail-closed: caches hold only redacted read models. Writers must call
``invalidate_*`` helpers; TTL bounds staleness when invalidation is missed.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


def stable_json_bytes(payload: Any) -> bytes:
    """Deterministic JSON bytes for ETag generation."""
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")


def weak_etag_from_payload(payload: Any) -> str:
    """Short weak ETag (RFC 7232 style) from a JSON-serializable payload."""
    digest = hashlib.sha256(stable_json_bytes(payload)).hexdigest()[:16]
    return f'W/"{digest}"'


def strong_etag_from_payload(payload: Any) -> str:
    """Strong ETag (quoted opaque token) from a JSON-serializable payload."""
    digest = hashlib.sha256(stable_json_bytes(payload)).hexdigest()[:32]
    return f'"{digest}"'


def normalize_etag_token(token: str) -> str:
    """Strip weak prefix for comparison (W/\"abc\" vs \"abc\")."""
    t = token.strip()
    if t.upper().startswith("W/"):
        t = t[2:].strip()
    return t


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match or not etag:
        return False
    candidate = if_none_match.strip()
    if len(candidate) > 4096:
        return False
    if candidate == "*":
        return True
    parts = [p.strip() for p in candidate.split(",")]
    target = normalize_etag_token(etag)
    for part in parts:
        if normalize_etag_token(part) == target:
            return True
        if part == etag:
            return True
    return False


def parse_entity_tags(header_value: str | None) -> tuple[str, ...]:
    """Parse If-None-Match / If-Match header into normalized tokens."""
    if not header_value or not str(header_value).strip():
        return ()
    raw = str(header_value).strip()
    if len(raw) > 4096:
        return ()
    if raw == "*":
        return ("*",)
    return tuple(p.strip() for p in raw.split(",") if p.strip())


@dataclass
class TtlEntry(Generic[T]):
    value: T
    expires_at: float
    etag: str = ""


@dataclass
class TtlSnapshotCache(Generic[T]):
    """Thread-safe TTL cache with optional ETag per entry."""

    ttl_seconds: float
    max_entries: int = 256
    _store: dict[str, TtlEntry[T]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, key: str) -> TtlEntry[T] | None:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._store[key]
                return None
            return entry

    def set(self, key: str, value: T, *, etag: str = "") -> TtlEntry[T]:
        now = time.monotonic()
        entry = TtlEntry(value=value, expires_at=now + self.ttl_seconds, etag=etag)
        with self._lock:
            if len(self._store) >= self.max_entries:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[key] = entry
        return entry

    def get_or_load(
        self,
        key: str,
        loader: Callable[[], T],
        *,
        etag_for: Callable[[T], str] | None = None,
    ) -> tuple[T, str]:
        cached = self.get(key)
        if cached is not None:
            return cached.value, cached.etag
        value = loader()
        etag = etag_for(value) if etag_for else weak_etag_from_payload(value)
        self.set(key, value, etag=etag)
        return value, etag

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            doomed = [k for k in self._store if k.startswith(prefix)]
            for key in doomed:
                del self._store[key]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class RevisionCounter:
    """Monotonic revision for cheap dirty detection (dashboard, receipts)."""

    def __init__(self) -> None:
        self._revision = 0
        self._lock = threading.Lock()

    def bump(self) -> int:
        with self._lock:
            self._revision += 1
            return self._revision

    @property
    def value(self) -> int:
        with self._lock:
            return self._revision

    def etag(self) -> str:
        return f'W/"rev-{self.value}"'


_receipt_read_cache: TtlSnapshotCache[dict[str, Any]] = TtlSnapshotCache(ttl_seconds=2.0, max_entries=512)
_experiment_dashboard_cache: TtlSnapshotCache[dict[str, Any]] = TtlSnapshotCache(ttl_seconds=1.5, max_entries=8)


def receipt_cache() -> TtlSnapshotCache[dict[str, Any]]:
    return _receipt_read_cache


def experiment_dashboard_cache() -> TtlSnapshotCache[dict[str, Any]]:
    return _experiment_dashboard_cache


def reset_read_caches_for_tests() -> None:
    _receipt_read_cache.clear()
    _experiment_dashboard_cache.clear()
