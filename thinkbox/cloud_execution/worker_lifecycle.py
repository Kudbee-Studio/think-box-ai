"""Cloud execution worker lifecycle — fail closed (PR #199)."""

from __future__ import annotations

from enum import Enum

from thinkbox.cloud_execution.errors import CloudExecutionError

WORKER_TERMINAL_STATES = frozenset({"STOPPED", "FAILED"})


class WorkerState(str, Enum):
    STARTING = "STARTING"
    IDLE = "IDLE"
    CLAIMING = "CLAIMING"
    EXECUTING = "EXECUTING"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


_ALLOWED: dict[WorkerState, frozenset[WorkerState]] = {
    WorkerState.STARTING: frozenset(
        {WorkerState.IDLE, WorkerState.DRAINING, WorkerState.STOPPED, WorkerState.FAILED},
    ),
    WorkerState.IDLE: frozenset(
        {WorkerState.CLAIMING, WorkerState.DRAINING, WorkerState.STOPPED, WorkerState.FAILED},
    ),
    WorkerState.CLAIMING: frozenset(
        {WorkerState.EXECUTING, WorkerState.IDLE, WorkerState.DRAINING, WorkerState.FAILED},
    ),
    WorkerState.EXECUTING: frozenset(
        {WorkerState.IDLE, WorkerState.DRAINING, WorkerState.FAILED},
    ),
    WorkerState.DRAINING: frozenset({WorkerState.STOPPED, WorkerState.FAILED}),
    WorkerState.STOPPED: frozenset(),
    WorkerState.FAILED: frozenset(),
}


def assert_worker_transition(current: WorkerState, target: WorkerState) -> None:
    if current in WORKER_TERMINAL_STATES:
        raise CloudExecutionError(
            error_type="InvalidWorkerTransition",
            context={
                "from": current.value,
                "to": target.value,
                "reason": "terminal",
            },
        )
    allowed = _ALLOWED.get(current, frozenset())
    if target not in allowed:
        raise CloudExecutionError(
            error_type="InvalidWorkerTransition",
            context={"from": current.value, "to": target.value},
        )


def worker_transition(current: WorkerState, target: WorkerState) -> WorkerState:
    assert_worker_transition(current, target)
    return target
