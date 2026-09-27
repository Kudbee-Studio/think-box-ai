"""Execution job lifecycle state machine — fail closed on invalid transitions (PR #197)."""

from __future__ import annotations

from thinkbox.cloud_execution.errors import InvalidTransitionError
from thinkbox.cloud_execution.job import ExecutionJobState, TERMINAL_STATES

_ALLOWED: dict[ExecutionJobState, frozenset[ExecutionJobState]] = {
    ExecutionJobState.QUEUED: frozenset(
        {ExecutionJobState.ADMITTED, ExecutionJobState.BLOCKED},
    ),
    ExecutionJobState.ADMITTED: frozenset(
        {ExecutionJobState.STARTING, ExecutionJobState.BLOCKED, ExecutionJobState.CANCELLED},
    ),
    ExecutionJobState.STARTING: frozenset(
        {ExecutionJobState.RUNNING, ExecutionJobState.FAILED, ExecutionJobState.BLOCKED},
    ),
    ExecutionJobState.RUNNING: frozenset(
        {
            ExecutionJobState.SUCCEEDED,
            ExecutionJobState.FAILED,
            ExecutionJobState.CANCELLED,
            ExecutionJobState.TIMED_OUT,
        },
    ),
    ExecutionJobState.SUCCEEDED: frozenset(),
    ExecutionJobState.FAILED: frozenset(),
    ExecutionJobState.CANCELLED: frozenset(),
    ExecutionJobState.TIMED_OUT: frozenset(),
    ExecutionJobState.BLOCKED: frozenset(),
}


def assert_transition(current: ExecutionJobState, target: ExecutionJobState) -> None:
    if current in TERMINAL_STATES:
        raise InvalidTransitionError(
            f"terminal state {current.value} cannot transition to {target.value}",
        )
    allowed = _ALLOWED.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            f"invalid transition {current.value} -> {target.value}",
        )


def transition(current: ExecutionJobState, target: ExecutionJobState) -> ExecutionJobState:
    assert_transition(current, target)
    return target
