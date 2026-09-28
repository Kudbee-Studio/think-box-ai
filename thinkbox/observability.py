"""Advanced observability: distributed tracing, metrics, profiling.

Provides OpenTelemetry-compatible tracing, Prometheus metrics,
and performance profiling for enterprise monitoring.
"""

from __future__ import annotations

import time
import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from collections import defaultdict
from datetime import datetime, timezone


@dataclass
class Span:
    """Distributed trace span."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ok"
    error: Optional[str] = None

    def finish(self) -> None:
        """Mark span as finished."""
        self.end_time = time.time()

    def duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        if self.end_time is None:
            return 0
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "duration_ms": self.duration_ms(),
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "error": self.error,
        }


class Tracer:
    """Distributed tracer for span management."""

    def __init__(self) -> None:
        self.spans: list[Span] = []
        self.current_span: Optional[Span] = None
        self._span_counter = 0

    def start_span(
        self,
        operation_name: str,
        attributes: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> Span:
        """Start a new span."""
        import uuid

        if trace_id is None:
            trace_id = str(uuid.uuid4())

        self._span_counter += 1
        span_id = f"{self._span_counter:016x}"

        parent_span_id = self.current_span.span_id if self.current_span else None

        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=time.time(),
            attributes=attributes or {},
        )

        self.spans.append(span)
        self.current_span = span
        return span

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        """Add event to current span."""
        if self.current_span:
            self.current_span.events.append({
                "name": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attributes": attributes or {},
            })

    def set_attribute(self, key: str, value: Any) -> None:
        """Set attribute on current span."""
        if self.current_span:
            self.current_span.attributes[key] = value

    def end_span(self, status: str = "ok", error: Optional[str] = None) -> Optional[Span]:
        """End current span."""
        if not self.current_span:
            return None

        self.current_span.finish()
        self.current_span.status = status
        self.current_span.error = error

        # Restore parent span
        if self.current_span.parent_span_id:
            for span in reversed(self.spans):
                if span.span_id == self.current_span.parent_span_id:
                    self.current_span = span
                    return self.current_span

        self.current_span = None
        return None

    def get_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """Get all spans for a trace."""
        return [s.to_dict() for s in self.spans if s.trace_id == trace_id]


class Metrics:
    """Prometheus-style metrics collection."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = defaultdict(list)
        self.timings: dict[str, list[float]] = defaultdict(list)

    def increment_counter(self, name: str, value: int = 1, labels: Optional[dict[str, str]] = None) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels)
        self.counters[key] += value

    def set_gauge(self, name: str, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Set a gauge."""
        key = self._make_key(name, labels)
        self.gauges[key] = value

    def record_histogram(self, name: str, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Record a histogram value."""
        key = self._make_key(name, labels)
        self.histograms[key].append(value)

    def record_timing(self, name: str, duration_ms: float, labels: Optional[dict[str, str]] = None) -> None:
        """Record operation timing."""
        key = self._make_key(name, labels)
        self.timings[key].append(duration_ms)

    def _make_key(self, name: str, labels: Optional[dict[str, str]]) -> str:
        """Create metric key with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_percentile(self, name: str, percentile: float = 50.0) -> Optional[float]:
        """Get percentile of timing/histogram."""
        key = next((k for k in self.timings.keys() if k.startswith(name)), None)
        if not key or not self.timings[key]:
            return None
        sorted_values = sorted(self.timings[key])
        index = int(len(sorted_values) * (percentile / 100))
        return sorted_values[min(index, len(sorted_values) - 1)]

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        # Counters
        for name, value in self.counters.items():
            lines.append(f"{name} {value}")

        # Gauges
        for name, value in self.gauges.items():
            lines.append(f"{name} {value}")

        # Histograms (as summary stats)
        for name, values in self.histograms.items():
            if values:
                lines.append(f"{name}_count {len(values)}")
                lines.append(f"{name}_sum {sum(values)}")
                lines.append(f"{name}_avg {sum(values) / len(values):.2f}")

        # Timings
        for name, values in self.timings.items():
            if values:
                lines.append(f"{name}_count {len(values)}")
                lines.append(f"{name}_sum_ms {sum(values):.2f}")
                lines.append(f"{name}_avg_ms {sum(values) / len(values):.2f}")
                lines.append(f"{name}_p50_ms {self.get_percentile(name, 50) or 0:.2f}")
                lines.append(f"{name}_p99_ms {self.get_percentile(name, 99) or 0:.2f}")

        return "\n".join(lines)


def traced(operation_name: Optional[str] = None) -> Callable:
    """Decorator for tracing operations."""
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = Tracer()
            span = tracer.start_span(op_name)
            try:
                result = func(*args, **kwargs)
                tracer.end_span(status="ok")
                return result
            except Exception as e:
                tracer.end_span(status="error", error=str(e))
                raise

        return wrapper
    return decorator


def timed(metrics: Metrics, operation_name: Optional[str] = None) -> Callable:
    """Decorator for recording operation timing."""
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start) * 1000
                metrics.record_timing(op_name, duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                metrics.record_timing(f"{op_name}_error", duration_ms)
                raise

        return wrapper
    return decorator


# Global instances
_tracer = Tracer()
_metrics = Metrics()


def get_tracer() -> Tracer:
    """Get global tracer."""
    return _tracer


def get_metrics() -> Metrics:
    """Get global metrics."""
    return _metrics
