"""Think Box lifecycle for THINK BOX AI."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ThinkBoxState(str, Enum):
    CREATED = "created"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThinkBoxLifecycle:
    @staticmethod
    def transition(think_box: Any, state: str) -> None:
        think_box.state = ThinkBoxState(state)

    @staticmethod
    def is_terminal(think_box: Any) -> bool:
        return think_box.state in (ThinkBoxState.COMPLETE, ThinkBoxState.FAILED, ThinkBoxState.CANCELLED)
