"""Hermetic observability counters for Think Job e2e (PR #183 F21)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ThinkJobE2eMetrics:
    jobs_simulated: int = 0
    retries_scheduled: int = 0
    cassettes_replayed: int = 0
    labels: dict[str, str] = field(default_factory=lambda: {"evidence": "simulated"})


def record_simulated_job(metrics: ThinkJobE2eMetrics) -> None:
    metrics.jobs_simulated += 1


def metrics_snapshot(metrics: ThinkJobE2eMetrics) -> dict[str, Any]:
    return {
        "jobs_simulated": metrics.jobs_simulated,
        "retries_scheduled": metrics.retries_scheduled,
        "cassettes_replayed": metrics.cassettes_replayed,
        "labels": dict(metrics.labels),
        "live_api_called": False,
    }
