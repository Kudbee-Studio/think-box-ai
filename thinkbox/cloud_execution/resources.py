"""Execution resource limits (PR #197)."""

from __future__ import annotations

from dataclasses import dataclass

from thinkbox.cloud_execution.errors import AdmissionDeniedError


@dataclass(frozen=True)
class ResourceLimits:
    cpu_cores: float
    memory_mb: int
    wall_clock_timeout_s: float
    max_concurrency: int

    def validate(self) -> None:
        if self.cpu_cores <= 0:
            raise AdmissionDeniedError("cpu_cores must be positive")
        if self.memory_mb <= 0:
            raise AdmissionDeniedError("memory_mb must be positive")
        if self.wall_clock_timeout_s <= 0:
            raise AdmissionDeniedError("wall_clock_timeout_s must be positive")
        if self.max_concurrency < 1:
            raise AdmissionDeniedError("max_concurrency must be >= 1")

    def snapshot(self) -> dict[str, float | int]:
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "wall_clock_timeout_s": self.wall_clock_timeout_s,
            "max_concurrency": self.max_concurrency,
        }
