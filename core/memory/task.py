"""Task memory adapter for THINK BOX AI."""

from __future__ import annotations

from typing import Any

from core.foundation.logging import get_logger
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer

logger = get_logger(__name__)


class TaskMemoryAdapter:
    def __init__(self, task_id: str, root_goal_id: str, agent_id: str, store: Any) -> None:
        self.task_id = task_id
        self.root_goal_id = root_goal_id
        self.agent_id = agent_id
        self.store = store
        self._entries: list[MemoryEntry] = []
        self.step_results: dict[str, dict[str, Any]] = {}
        self.validation_outcomes: dict[str, bool] = {}
        self.replan_history: list[dict[str, Any]] = []
        self.error_log: list[dict[str, Any]] = []
        self.status: str = "running"

    def record_step_result(self, step_id: str, result: dict[str, Any]) -> None:
        self.step_results[step_id] = result
        entry = MemoryEntry(
            key=f"task:{self.task_id}:step:{step_id}",
            layer=MemoryLayer.TASK,
            entry_type=MemoryEntryType.REASONING_STEP,
            value=result,
            agent_id=self.agent_id,
            task_id=self.task_id,
        )
        self._entries.append(entry)
        if self.store:
            self.store.put(entry)

    def record_validation(self, step_id: str, passed: bool) -> None:
        self.validation_outcomes[step_id] = passed
        entry = MemoryEntry(
            key=f"task:{self.task_id}:validation:{step_id}",
            layer=MemoryLayer.TASK,
            entry_type=MemoryEntryType.GOAL_STATE,
            value={"step_id": step_id, "passed": passed},
            agent_id=self.agent_id,
            task_id=self.task_id,
        )
        self._entries.append(entry)
        if self.store:
            self.store.put(entry)

    def record_error(self, error: str, context: dict[str, Any] | None = None) -> None:
        self.error_log.append({"error": error, "context": context or {}})
        entry = MemoryEntry(
            key=f"task:{self.task_id}:error:{len(self.error_log)}",
            layer=MemoryLayer.TASK,
            entry_type=MemoryEntryType.ERROR,
            value={"error": error, "context": context or {}},
            agent_id=self.agent_id,
            task_id=self.task_id,
        )
        self._entries.append(entry)
        if self.store:
            self.store.put(entry)

    def get_recent(self, limit: int = 20) -> list[MemoryEntry]:
        return self._entries[-limit:]

    def flush(self) -> None:
        logger.debug("Flushing task memory", extra={"task_id": self.task_id, "count": len(self._entries)})
