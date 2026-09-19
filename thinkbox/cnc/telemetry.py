"""Telemetry ingest stub for CNC manufacturing — simulated time-series only."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TelemetryPoint:
    timestamp: str
    metric: str
    value: float
    unit: str = ""
    evidence_label: str = "simulated"
    job_id: str = ""

    def model_dump(self) -> dict[str, Any]:
        return {"timestamp": self.timestamp, "metric": self.metric, "value": self.value, "unit": self.unit, "evidence_label": self.evidence_label, "job_id": self.job_id}


@dataclass
class TelemetrySeries:
    metric: str
    points: list[TelemetryPoint] = field(default_factory=list)

    def append(self, point: TelemetryPoint) -> None:
        self.points.append(point)

    def model_dump(self) -> dict[str, Any]:
        return {"metric": self.metric, "points": [p.model_dump() for p in self.points]}


class TelemetryIngest:
    """Time-series store for CNC telemetry.

    Only simulated evidence is accepted. No physical measurements are stored.
    """

    def __init__(self, storage_path: str = "data/cnc/telemetry") -> None:
        self.storage_path = Path(storage_path)
        self._series: dict[str, TelemetrySeries] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        for f in self.storage_path.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                series = TelemetrySeries(metric=data["metric"])
                for p in data.get("points", []):
                    point = TelemetryPoint(**p)
                    series.points.append(point)
                self._series[series.metric] = series
            except (json.JSONDecodeError, ValueError, KeyError):
                continue

    def _save(self, series: TelemetrySeries) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        f = self.storage_path / f"{series.metric.replace('.', '_')}.json"
        f.write_text(json.dumps(series.model_dump(), indent=2))

    def append(self, point: TelemetryPoint) -> None:
        if point.evidence_label not in ("simulated",):
            raise ValueError(f"Unsupported evidence_label: {point.evidence_label}. Only 'simulated' is accepted.")
        if point.metric not in self._series:
            self._series[point.metric] = TelemetrySeries(metric=point.metric)
        self._series[point.metric].append(point)
        self._save(self._series[point.metric])

    def query(self, metric: str, start: str | None = None, end: str | None = None) -> list[TelemetryPoint]:
        series = self._series.get(metric, TelemetrySeries(metric=metric))
        results = list(series.points)
        if start:
            results = [p for p in results if p.timestamp >= start]
        if end:
            results = [p for p in results if p.timestamp <= end]
        return results

    def summarize(self, metric: str) -> dict[str, Any]:
        points = self.query(metric)
        if not points:
            return {"metric": metric, "count": 0, "evidence_label": "simulated"}
        values = [p.value for p in points]
        return {
            "metric": metric,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "evidence_label": "simulated",
        }
