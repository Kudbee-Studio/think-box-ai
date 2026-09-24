"""Retry policy for durable queue (PR #198)."""

from __future__ import annotations

from dataclasses import dataclass

from thinkbox.cloud_execution.errors import CloudExecutionError
from thinkbox.cloud_execution.job import ExecutionJobState


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    retryable_exit_codes: frozenset[int] = frozenset({1, 2})

    def validate(self) -> None:
        if self.max_retries < 0:
            raise CloudExecutionError(
                error_type="InvalidRetryPolicy",
                context={"reason": "max_retries must be >= 0"},
            )

    def is_retryable(
        self,
        terminal_state: ExecutionJobState,
        exit_code: int | None,
        metadata: dict[str, object],
    ) -> bool:
        if terminal_state in (ExecutionJobState.CANCELLED, ExecutionJobState.SUCCEEDED):
            return False
        if terminal_state == ExecutionJobState.TIMED_OUT:
            return False
        if terminal_state == ExecutionJobState.BLOCKED:
            return False
        if terminal_state != ExecutionJobState.FAILED:
            return False
        if metadata.get("retryable") is False:
            return False
        if metadata.get("retryable") is True:
            return True
        return exit_code in self.retryable_exit_codes

    def may_retry(self, attempt_count: int) -> bool:
        return attempt_count < self.max_retries
