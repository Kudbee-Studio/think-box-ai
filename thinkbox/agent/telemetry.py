"""KILO Cloud Agent Telemetry & Observability.

Metrics (Prometheus-compatible), traces (OTEL-compatible),
structured logging, and health endpoints.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TelemetryLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class MetricRecord:
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000


@dataclass
class LogEntry:
    level: TelemetryLevel
    message: str
    agent_id: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


class TelemetryEmitter:
    """
    Telemetry emitter for metrics, traces, and logs.

    Collects and emits:
    - Metrics: counter, gauge, histogram, summary
    - Traces: distributed tracing spans
    - Logs: structured log entries
    - Health: agent health check data
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        tenant_id: str,
        endpoint: str = "localhost:4317",
    ) -> None:
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.tenant_id = tenant_id
        self.endpoint = endpoint

        self._metrics: List[MetricRecord] = []
        self._spans: Dict[str, Span] = {}
        self._logs: List[LogEntry] = []
        self._counter_values: Dict[str, float] = {}
        self._gauge_values: Dict[str, float] = {}
        self._histogram_values: Dict[str, List[float]] = {}
        self._running = False
        self._lock = threading.Lock()
        self._flush_count = 0
        self._started_at: Optional[float] = None

    def counter(
        self, name: str, value: float = 1.0, labels: Dict[str, str] | None = None
    ) -> None:
        with self._lock:
            key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self._counter_values[key] = self._counter_values.get(key, 0.0) + value
            self._metrics.append(
                MetricRecord(name=name, value=value, labels=labels or {})
            )

    def gauge(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        with self._lock:
            key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self._gauge_values[key] = value
            self._metrics.append(
                MetricRecord(name=name, value=value, labels=labels or {})
            )

    def histogram(
        self, name: str, value: float, labels: Dict[str, str] | None = None
    ) -> None:
        with self._lock:
            key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            if key not in self._histogram_values:
                self._histogram_values[key] = []
            self._histogram_values[key].append(value)
            self._metrics.append(
                MetricRecord(name=name, value=value, labels=labels or {})
            )

    def get_counter(self, name: str, labels: Dict[str, str] | None = None) -> float:
        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
        return self._counter_values.get(key, 0.0)

    def get_gauge(self, name: str, labels: Dict[str, str] | None = None) -> float:
        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
        return self._gauge_values.get(key, 0.0)

    def start_trace(
        self,
        operation_name: str,
        parent_span_id: Optional[str] = None,
        tags: Dict[str, Any] | None = None,
    ) -> Span:
        trace_id = uuid.uuid4().hex[:32]
        span_id = uuid.uuid4().hex[:16]
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=time.time(),
            tags=tags or {},
        )
        with self._lock:
            self._spans[span_id] = span
        logger.debug(f"Started trace: {operation_name} span={span_id}")
        return span

    def end_trace(self, span_id: str, tags: Dict[str, Any] | None = None) -> Optional[Span]:
        with self._lock:
            span = self._spans.get(span_id)
            if span is None:
                return None
            span.end_time = time.time()
            if tags:
                span.tags.update(tags)
        logger.debug(f"Ended trace: {span.operation_name} span={span_id} duration={span.duration_ms:.2f}ms")
        return span

    def add_span_log(self, span_id: str, level: TelemetryLevel, message: str, data: Dict[str, Any] | None = None) -> bool:
        with self._lock:
            span = self._spans.get(span_id)
            if span is None:
                return False
            span.logs.append({
                "level": level.value,
                "message": message,
                "data": data or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return True

    def emit_lifecycle_event(
        self,
        old_state: str,
        new_state: str,
    ) -> None:
        self.counter(
            "agent.lifecycle.transitions",
            labels={"from": old_state, "to": new_state},
        )
        span = self.start_trace(
            f"lifecycle:{old_state}_to_{new_state}",
            tags={"from": old_state, "to": new_state},
        )
        span.tags["agent_id"] = self.agent_id
        self.end_trace(span.span_id, tags={"duration_category": "lifecycle"})
        self.log(
            TelemetryLevel.INFO,
            f"Agent lifecycle: {old_state} -> {new_state}",
            data={"from": old_state, "to": new_state},
        )

    def log(
        self,
        level: TelemetryLevel,
        message: str,
        data: Dict[str, Any] | None = None,
    ) -> LogEntry:
        entry = LogEntry(
            level=level,
            message=message,
            agent_id=self.agent_id,
            data=data or {},
        )
        with self._lock:
            self._logs.append(entry)
        logger.log(
            getattr(logging, level.value, logging.INFO),
            f"[{self.agent_id}] {message}",
            extra={"agent_data": data or {}},
        )
        return entry

    def health_check(self) -> dict[str, Any]:
        with self._lock:
            return {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type,
                "tenant_id": self.tenant_id,
                "running": self._running,
                "uptime_seconds": time.time() - self._started_at if self._started_at else 0,
                "metrics_count": len(self._metrics),
                "spans_count": len(self._spans),
                "logs_count": len(self._logs),
                "endpoint": self.endpoint,
            }

    def flush(self) -> int:
        with self._lock:
            count = len(self._metrics)
            if self._running:
                self._running = False
            self._flush_count += 1
        logger.info(f"Telemetry flush: {count} metrics, flush #{self._flush_count}")
        return count

    def stop(self) -> None:
        self._running = False
        logger.info(f"Telemetry stopped for agent {self.agent_id}")

    def start(self) -> None:
        self._running = True
        self._started_at = time.time()
        logger.info(f"Telemetry started for agent {self.agent_id}")

    def is_running(self) -> bool:
        return self._running

    def get_metrics(self) -> List[MetricRecord]:
        with self._lock:
            return list(self._metrics)

    def get_spans(self) -> List[Span]:
        with self._lock:
            return list(self._spans.values())

    def get_logs(
        self,
        level: TelemetryLevel | None = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        with self._lock:
            logs = self._logs
            if level is not None:
                logs = [l for l in logs if l.level == level]
            return logs[-limit:]

    def get_telemetry_summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "agent_id": self.agent_id,
                "metrics_total": len(self._metrics),
                "spans_total": len(self._spans),
                "logs_total": len(self._logs),
                "counter_keys": len(self._counter_values),
                "gauge_keys": len(self._gauge_values),
                "histogram_keys": len(self._histogram_values),
                "flush_count": self._flush_count,
                "running": self._running,
            }
