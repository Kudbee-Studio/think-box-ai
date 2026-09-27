"""Worker orchestrator configuration (PR #199)."""

from __future__ import annotations

from dataclasses import dataclass

from thinkbox.cloud_execution.errors import CloudExecutionError


@dataclass(frozen=True)
class WorkerConfig:
    worker_id: str
    max_active_jobs: int = 1
    heartbeat_interval_s: float = 1.0
    heartbeat_timeout_s: float = 5.0
    claim_renewal_fraction: float = 0.5

    def validate(self) -> None:
        if not self.worker_id.strip():
            raise CloudExecutionError(
                error_type="InvalidWorkerConfig",
                context={"reason": "worker_id required"},
            )
        if self.max_active_jobs < 1:
            raise CloudExecutionError(
                error_type="InvalidWorkerConfig",
                context={"reason": "max_active_jobs must be >= 1"},
            )
        if self.heartbeat_interval_s <= 0 or self.heartbeat_timeout_s <= 0:
            raise CloudExecutionError(
                error_type="InvalidWorkerConfig",
                context={"reason": "heartbeat intervals must be positive"},
            )
        if not 0.0 < self.claim_renewal_fraction <= 1.0:
            raise CloudExecutionError(
                error_type="InvalidWorkerConfig",
                context={"reason": "claim_renewal_fraction out of range"},
            )
