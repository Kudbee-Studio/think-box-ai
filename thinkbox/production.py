"""ThinkBox Phase 10 — Production Hardening & Observability.

Features:
1. HealthCheckSystem — Liveness and readiness probes with dependency checks
2. MetricsCollector — Prometheus-compatible counters, gauges, histograms
3. GracefulShutdown — Drain in-flight work, flush buffers, stop accepting
4. ConfigValidation — Startup schema validation with typed settings
5. ErrorRecovery — Retry with exponential backoff and circuit breaker
6. RequestDeduplication — Idempotency keys and duplicate suppression
7. Tracing — Distributed spans, context propagation, trace aggregation
8. RateLimiter — Token bucket and sliding window rate limiters
9. LoadBalancer — Round-robin, least-connections, and health-checked backends
10. AlertManager — Threshold alerts, routing, and suppression windows
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Coroutine


# ---------------------------------------------------------------------------
# 1. HealthCheckSystem
# ---------------------------------------------------------------------------

@dataclass
class HealthStatus:
    component: str
    healthy: bool
    message: str
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class HealthCheckSystem:
    def __init__(self) -> None:
        self._checks: dict[str, Callable[[], HealthStatus]] = {}
        self._lock = threading.RLock()

    def register(self, component: str, check: Callable[[], HealthStatus]) -> None:
        with self._lock:
            self._checks[component] = check

    def check(self, component: str) -> HealthStatus:
        with self._lock:
            fn = self._checks.get(component)
            if fn is None:
                return HealthStatus(component=component, healthy=False, message="not_registered")
            return fn()

    def liveness(self) -> dict[str, Any]:
        return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}

    def readiness(self) -> dict[str, Any]:
        with self._lock:
            results = [self.check(name) for name in self._checks]
        ready = all(r.healthy for r in results)
        return {
            "status": "ready" if ready else "not_ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {r.component: {"healthy": r.healthy, "message": r.message} for r in results},
        }


# ---------------------------------------------------------------------------
# 2. MetricsCollector
# ---------------------------------------------------------------------------

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class MetricSample:
    name: str
    kind: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class MetricsCollector:
    def __init__(self, max_samples: int = 10000) -> None:
        self._samples: deque[MetricSample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def increment(self, name: str, amount: float = 1.0, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._samples.append(MetricSample(name=name, kind=MetricType.COUNTER.value, value=amount, labels=labels or {}))

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._samples.append(MetricSample(name=name, kind=MetricType.GAUGE.value, value=value, labels=labels or {}))

    def histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            self._samples.append(MetricSample(name=name, kind=MetricType.HISTOGRAM.value, value=value, labels=labels or {}))

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [s.__dict__ for s in self._samples]

    def render_prometheus(self) -> str:
        with self._lock:
            lines = []
            for sample in self._samples:
                labels = ",".join(f'{k}="{v}"' for k, v in sample.labels.items())
                if labels:
                    labels = "{" + labels + "}"
                lines.append(f"{sample.name}{labels} {sample.value}")
            return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. GracefulShutdown
# ---------------------------------------------------------------------------

class GracefulShutdown:
    def __init__(self, drain_timeout: float = 5.0) -> None:
        self._drain_timeout = drain_timeout
        self._active = 0
        self._draining = False
        self._lock = threading.Lock()
        self._flush_callbacks: list[Callable[[], None]] = []

    def register_flush(self, callback: Callable[[], None]) -> None:
        self._flush_callbacks.append(callback)

    def begin(self) -> None:
        with self._lock:
            self._draining = True

    def acquire(self) -> bool:
        with self._lock:
            if self._draining:
                return False
            self._active += 1
            return True

    def release(self) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)

    def drain(self) -> dict[str, Any]:
        start = time.time()
        with self._lock:
            self._draining = True
        while True:
            with self._lock:
                if self._active == 0:
                    break
            if time.time() - start > self._drain_timeout:
                break
            time.sleep(0.05)
        for cb in self._flush_callbacks:
            cb()
        return {
            "status": "drained",
            "active_remaining": self._active,
            "elapsed": round(time.time() - start, 4),
        }


# ---------------------------------------------------------------------------
# 4. ConfigValidation
# ---------------------------------------------------------------------------

@dataclass
class ValidatedConfig:
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)


class ConfigValidation:
    def __init__(self, schema: dict[str, Any]) -> None:
        self._schema = schema

    def validate(self, config: dict[str, Any]) -> ValidatedConfig:
        errors: list[str] = []
        data: dict[str, Any] = {}
        for key, rule in self._schema.items():
            if key not in config:
                if rule.get("required", False):
                    errors.append(f"missing required key: {key}")
                continue
            value = config[key]
            expected = rule.get("type")
            if expected == "int" and not isinstance(value, int):
                errors.append(f"{key} must be int")
            elif expected == "float" and not isinstance(value, (int, float)):
                errors.append(f"{key} must be float")
            elif expected == "str" and not isinstance(value, str):
                errors.append(f"{key} must be str")
            elif expected == "bool" and not isinstance(value, bool):
                errors.append(f"{key} must be bool")
            elif expected == "list" and not isinstance(value, list):
                errors.append(f"{key} must be list")
            if "min" in rule and isinstance(value, (int, float)) and value < rule["min"]:
                errors.append(f"{key} below minimum {rule['min']}")
            if "max" in rule and isinstance(value, (int, float)) and value > rule["max"]:
                errors.append(f"{key} above maximum {rule['max']}")
            data[key] = value
        return ValidatedConfig(data=data, errors=errors)


# ---------------------------------------------------------------------------
# 5. ErrorRecovery
# ---------------------------------------------------------------------------

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self._threshold = failure_threshold
        self._recovery = recovery_timeout
        self._failures = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self._failures >= self._threshold:
                if time.time() - self._opened_at >= self._recovery:
                    self._failures = 0
                    return True
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = time.time()


class ErrorRecovery:
    def __init__(self, max_retries: int = 3, base_delay: float = 0.1) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def execute(self, key: str, fn: Callable[[], Any], retries: int | None = None) -> Any:
        retries = retries if retries is not None else self._max_retries
        with self._lock:
            if key not in self._breakers:
                self._breakers[key] = CircuitBreaker()
        for attempt in range(retries + 1):
            with self._lock:
                if not self._breakers[key].allow():
                    raise RuntimeError(f"circuit_open:{key}")
            try:
                result = fn()
            except Exception:
                with self._lock:
                    self._breakers[key].record_failure()
                if attempt == retries:
                    raise
                time.sleep(self._base_delay * (2 ** attempt))
                continue
            with self._lock:
                self._breakers[key].record_success()
            return result
        raise RuntimeError("unreachable")

    def circuit_state(self, key: str) -> dict[str, Any]:
        with self._lock:
            breaker = self._breakers.get(key)
            if breaker is None:
                return {"state": "unknown"}
            return {
                "state": "open" if breaker._failures >= breaker._threshold else "closed",
                "failures": breaker._failures,
            }


# ---------------------------------------------------------------------------
# 6. RequestDeduplication
# ---------------------------------------------------------------------------

@dataclass
class DedupEntry:
    key: str
    response: Any
    created_at: str
    expires_at: str


class RequestDeduplication:
    def __init__(self, default_ttl: float = 60.0, max_entries: int = 10000) -> None:
        self._ttl = default_ttl
        self._max = max_entries
        self._entries: dict[str, DedupEntry] = {}
        self._lock = threading.Lock()

    def _make_key(self, method: str, path: str, body_hash: str) -> str:
        return f"{method}:{path}:{body_hash}"

    def process(self, method: str, path: str, body: Any, compute_response: Callable[[], Any]) -> Any:
        body_hash = hashlib.sha256(str(body).encode()).hexdigest()[:16]
        key = self._make_key(method, path, body_hash)
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._entries.get(key)
            if entry and datetime.fromisoformat(entry.expires_at) > now:
                return entry.response
        response = compute_response()
        entry = DedupEntry(
            key=key,
            response=response,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self._ttl)).isoformat(),
        )
        with self._lock:
            self._entries[key] = entry
            if len(self._entries) > self._max:
                oldest = min(self._entries, key=lambda k: self._entries[k].created_at)
                del self._entries[oldest]
        return response

    def invalidate(self, method: str, path: str, body: Any) -> None:
        body_hash = hashlib.sha256(str(body).encode()).hexdigest()[:16]
        key = self._make_key(method, path, body_hash)
        with self._lock:
            self._entries.pop(key, None)


# ---------------------------------------------------------------------------
# 7. Tracing
# ---------------------------------------------------------------------------

@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation: str
    start_time: float
    end_time: float | None = None
    tags: dict[str, str] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)

    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000.0


class Tracing:
    def __init__(self, max_spans: int = 5000) -> None:
        self._spans: deque[Span] = deque(maxlen=max_spans)
        self._context = threading.local()
        self._lock = threading.Lock()

    def start_span(self, operation: str, parent_span_id: str | None = None) -> Span:
        trace_id = getattr(self._context, "trace_id", None) or uuid.uuid4().hex[:16]
        self._context.trace_id = trace_id
        span = Span(
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:12],
            parent_span_id=parent_span_id,
            operation=operation,
            start_time=time.time(),
        )
        with self._lock:
            self._spans.append(span)
        return span

    def end_span(self, span: Span) -> None:
        span.end_time = time.time()

    def log(self, span: Span, event: str, payload: dict[str, Any] | None = None) -> None:
        span.logs.append({"event": event, "payload": payload or {}, "timestamp": time.time()})

    def trace(self) -> dict[str, Any]:
        with self._lock:
            spans = [s.__dict__ for s in self._spans]
        return {"trace_id": getattr(self._context, "trace_id", None), "spans": spans}


# ---------------------------------------------------------------------------
# 8. RateLimiter
# ---------------------------------------------------------------------------

class TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last = time.time()
        self._lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self._last
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._last = now
            if self._tokens >= amount:
                self._tokens -= amount
                return True
            return False


class SlidingWindow:
    def __init__(self, limit: int, window: float) -> None:
        self._limit = limit
        self._window = window
        self._hits: deque[float] = deque()

    def allow(self) -> bool:
        now = time.time()
        while self._hits and now - self._hits[0] > self._window:
            self._hits.popleft()
        if len(self._hits) < self._limit:
            self._hits.append(now)
            return True
        return False


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._windows: dict[str, SlidingWindow] = {}
        self._lock = threading.Lock()

    def bucket(self, key: str, rate: float, capacity: float) -> TokenBucket:
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(rate=rate, capacity=capacity)
            return self._buckets[key]

    def window(self, key: str, limit: int, window: float) -> SlidingWindow:
        with self._lock:
            if key not in self._windows:
                self._windows[key] = SlidingWindow(limit=limit, window=window)
            return self._windows[key]


# ---------------------------------------------------------------------------
# 9. LoadBalancer
# ---------------------------------------------------------------------------

@dataclass
class Backend:
    name: str
    address: str
    weight: int = 1
    healthy: bool = True
    active_connections: int = 0
    last_check: str = ""


class LoadBalancer:
    def __init__(self, strategy: str = "round_robin") -> None:
        self._strategy = strategy
        self._backends: list[Backend] = []
        self._index = 0
        self._lock = threading.Lock()

    def add_backend(self, backend: Backend) -> None:
        with self._lock:
            self._backends.append(backend)

    def remove_backend(self, name: str) -> None:
        with self._lock:
            self._backends = [b for b in self._backends if b.name != name]

    def select(self) -> Backend | None:
        with self._lock:
            candidates = [b for b in self._backends if b.healthy]
            if not candidates:
                return None
            if self._strategy == "round_robin":
                backend = candidates[self._index % len(candidates)]
                self._index += 1
                return backend
            if self._strategy == "least_connections":
                return min(candidates, key=lambda b: b.active_connections)
            return candidates[0]

    def mark(self, name: str, healthy: bool) -> None:
        with self._lock:
            for b in self._backends:
                if b.name == name:
                    b.healthy = healthy


# ---------------------------------------------------------------------------
# 10. AlertManager
# ---------------------------------------------------------------------------

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    alert_id: str
    name: str
    severity: str
    message: str
    value: float
    threshold: float
    timestamp: str
    suppressed: bool = False


class AlertManager:
    def __init__(self, suppression_window: float = 60.0) -> None:
        self._alerts: list[Alert] = []
        self._suppression = suppression_window
        self._last_fired: dict[str, float] = {}
        self._lock = threading.Lock()

    def evaluate(self, name: str, value: float, threshold: float, severity: AlertSeverity = AlertSeverity.WARNING) -> Alert | None:
        fired = value >= threshold
        now = time.time()
        with self._lock:
            last = self._last_fired.get(name, 0.0)
            if fired and (now - last) >= self._suppression:
                alert = Alert(
                    alert_id=f"alert_{uuid.uuid4().hex[:12]}",
                    name=name,
                    severity=severity.value,
                    message=f"{name} exceeded threshold {threshold}",
                    value=value,
                    threshold=threshold,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                self._alerts.append(alert)
                self._last_fired[name] = now
                return alert
        return None

    def alerts(self, severity: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = self._alerts
        if severity:
            items = [a for a in items if a.severity == severity]
        return [a.__dict__ for a in items[-limit:]]
