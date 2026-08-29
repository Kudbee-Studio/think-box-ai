"""Observability — structured logging + metrics for KUDBEE."""

from __future__ import annotations
import json
import time
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)


class StructuredLogger:
    """JSON structured logger for machine-readable logs."""

    def __init__(self, service: str = "kudbee") -> None:
        self._service = service

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            "level": level,
            "service": self._service,
            "message": message,
            **kwargs,
        }
        print(json.dumps(entry), flush=True)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log("ERROR", message, **kwargs)

    def metric(self, name: str, value: float, **tags: Any) -> None:
        self._log("METRIC", f"metric:{name}", metric_name=name, metric_value=value, **tags)


class MetricsCollector:
    """Prometheus-compatible metrics collection.
    
    Tracks request counts, latencies, and token operations.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def record_latency(self, name: str, duration_ms: float) -> None:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(duration_ms)

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    name: {
                        "count": len(values),
                        "avg_ms": round(sum(values) / max(1, len(values)), 2),
                        "p95_ms": round(sorted(values)[int(len(values) * 0.95)] if values else 0, 2),
                        "max_ms": round(max(values) if values else 0, 2),
                    }
                    for name, values in self._histograms.items()
                },
            }

    def format_prometheus(self) -> str:
        """Format metrics in Prometheus exposition format."""
        lines = []
        with self._lock:
            for name, value in self._counters.items():
                lines.append(f"kudbee_{name}_total {value}")
            for name, value in self._gauges.items():
                lines.append(f"kudbee_{name} {value}")
            for name, values in self._histograms.items():
                if values:
                    lines.append(f"kudbee_{name}_count {len(values)}")
                    lines.append(f"kudbee_{name}_sum {sum(values)}")
        return "\n".join(lines)


# Global instances
structured_log = StructuredLogger()
metrics = MetricsCollector()
