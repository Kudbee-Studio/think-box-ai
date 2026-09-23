"""Control-plane API / ops hardening helpers (PR #157).

Fail-closed envelopes, query clamping, in-memory rate windows, idempotency keys,
and log-safe redaction. Hermetic only — ``live_api_called=False`` on defaults.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping

from thinkbox.control_plane_api_contract import (
    CONTROL_PLANE_API_VERSION,
    ControlPlaneApiError,
    error_envelope,
)

__all__ = (
    "OPS_HARDEN_LABEL",
    "OPS_HARDEN_VERSION",
    "DEFAULT_CHAIN_LIMIT",
    "MAX_CHAIN_LIMIT",
    "DEFAULT_RATE_LIMIT_PER_MINUTE",
    "IdempotencyConflict",
    "IdempotencyRegistry",
    "OpsRateLimitExceeded",
    "OpsRateLimitWindow",
    "assert_prev_receipt_link",
    "clamp_query_limit",
    "fingerprint_idempotency_body",
    "get_idempotency_registry",
    "get_ops_rate_limiter",
    "http_exception_detail",
    "redact_mapping_for_logs",
    "reset_idempotency_registry",
    "reset_ops_rate_limiter",
)

OPS_HARDEN_LABEL = "api-ops-harden"
OPS_HARDEN_VERSION = "1.0.0"

DEFAULT_CHAIN_LIMIT = 50
MAX_CHAIN_LIMIT = 200
DEFAULT_RATE_LIMIT_PER_MINUTE = 120

_SECRET_KEY_RE = re.compile(
    r"(token|secret|password|api[_-]?key|authorization|bearer)",
    re.IGNORECASE,
)


def clamp_query_limit(
    limit: int | None,
    *,
    default: int = DEFAULT_CHAIN_LIMIT,
    maximum: int = MAX_CHAIN_LIMIT,
) -> int:
    """Bound list/page limits for abuse resistance."""
    if limit is None:
        return default
    try:
        value = int(limit)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return 1
    return min(value, maximum)


def redact_mapping_for_logs(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-redact likely secrets for operator logs."""
    out: dict[str, Any] = {}

    def _walk(key: str, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): _walk(str(k), v) for k, v in value.items()}
        if isinstance(value, list):
            return [_walk(key, item) for item in value]
        if _SECRET_KEY_RE.search(key):
            if value is None:
                return None
            text = str(value)
            if len(text) <= 4:
                return "***"
            return text[:2] + "…" + text[-2:]
        if isinstance(value, str) and value.lower().startswith("bearer "):
            return "Bearer ***"
        return value

    for k, v in payload.items():
        out[str(k)] = _walk(str(k), v)
    return out


def http_exception_detail(
    error: ControlPlaneApiError,
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """FastAPI HTTPException detail payload (always structured envelope)."""
    return error_envelope(error, request_id=request_id, live_api_called=False)


def fingerprint_idempotency_body(body: Mapping[str, Any]) -> str:
    """Stable hash for idempotent POST replay detection."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class IdempotencyConflict(ValueError):
    """Same idempotency key reused with a different body."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"idempotency_conflict:{key}")


@dataclass
class _IdempotencyEntry:
    operation_id: str
    body_fingerprint: str
    created_at: float = field(default_factory=time.monotonic)


class IdempotencyRegistry:
    """In-memory idempotency key → operation mapping (hermetic)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[str, _IdempotencyEntry] = {}

    def register(
        self,
        key: str,
        *,
        operation_id: str,
        body: Mapping[str, Any],
    ) -> None:
        fp = fingerprint_idempotency_body(body)
        with self._lock:
            existing = self._keys.get(key)
            if existing is None:
                self._keys[key] = _IdempotencyEntry(operation_id=operation_id, body_fingerprint=fp)
                return
            if existing.body_fingerprint != fp:
                raise IdempotencyConflict(key)
            if existing.operation_id != operation_id:
                raise IdempotencyConflict(key)

    def lookup(self, key: str) -> str | None:
        with self._lock:
            entry = self._keys.get(key)
            return entry.operation_id if entry else None

    def clear(self) -> None:
        with self._lock:
            self._keys.clear()


_idempotency_registry: IdempotencyRegistry | None = None
_idempotency_lock = threading.Lock()


def get_idempotency_registry() -> IdempotencyRegistry:
    global _idempotency_registry
    with _idempotency_lock:
        if _idempotency_registry is None:
            _idempotency_registry = IdempotencyRegistry()
        return _idempotency_registry


def reset_idempotency_registry() -> None:
    global _idempotency_registry
    with _idempotency_lock:
        if _idempotency_registry is not None:
            _idempotency_registry.clear()
        _idempotency_registry = None


class OpsRateLimitExceeded(Exception):
    """Client exceeded hermetic ops rate window."""

    def __init__(self, client_key: str, retry_after_seconds: float) -> None:
        self.client_key = client_key
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate_limit:{client_key}")


class OpsRateLimitWindow:
    """Fixed-window request counter per client key (process-local)."""

    def __init__(self, *, max_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE) -> None:
        self._max = max(1, int(max_per_minute))
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[int, float]] = {}

    def check(self, client_key: str) -> None:
        now = time.monotonic()
        with self._lock:
            count, window_start = self._windows.get(client_key, (0, now))
            if now - window_start >= 60.0:
                count = 0
                window_start = now
            count += 1
            self._windows[client_key] = (count, window_start)
            if count > self._max:
                retry = max(1.0, 60.0 - (now - window_start))
                raise OpsRateLimitExceeded(client_key, retry_after_seconds=retry)

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


_ops_rate_limiter: OpsRateLimitWindow | None = None
_rate_lock = threading.Lock()


def get_ops_rate_limiter() -> OpsRateLimitWindow:
    global _ops_rate_limiter
    with _rate_lock:
        if _ops_rate_limiter is None:
            _ops_rate_limiter = OpsRateLimitWindow()
        return _ops_rate_limiter


def reset_ops_rate_limiter() -> None:
    global _ops_rate_limiter
    with _rate_lock:
        if _ops_rate_limiter is not None:
            _ops_rate_limiter.reset()
        _ops_rate_limiter = None


def assert_prev_receipt_link(
    receipt: Mapping[str, Any],
    *,
    expected_prev_receipt_id: str | None,
) -> None:
    """Fail-closed when paginated prev_receipt_id does not match chain order."""
    actual = receipt.get("prev_receipt_id")
    if actual != expected_prev_receipt_id:
        raise ValueError(
            f"prev_receipt_link_mismatch:{receipt.get('receipt_id')}:{actual}!={expected_prev_receipt_id}",
        )


def ops_harden_contract_snippet() -> dict[str, Any]:
    """Embedded in GET /contract for operator discovery."""
    return {
        "ops_harden": OPS_HARDEN_LABEL,
        "ops_harden_version": OPS_HARDEN_VERSION,
        "api_version": CONTROL_PLANE_API_VERSION,
        "features": [
            "structured_error_envelopes",
            "query_limit_clamp",
            "idempotency_key_header",
            "ops_rate_limit_window",
            "log_redaction",
        ],
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
