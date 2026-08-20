"""Session memory adapter for THINK BOX AI."""

from __future__ import annotations

from typing import Any

from core.foundation.logging import get_logger
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer

logger = get_logger(__name__)


class SessionMemoryAdapter:
    def __init__(self, session_id: str, agent_id: str, store: Any) -> None:
        self.session_id = session_id
        self.agent_id = agent_id
        self.store = store
        self._entries: list[MemoryEntry] = []

    def add_reasoning(self, thought: str, metadata: dict[str, Any] | None = None) -> MemoryEntry:
        entry = MemoryEntry(
            key=f"session:{self.session_id}:reasoning:{len(self._entries)}",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.REASONING_STEP,
            value={"thought": thought},
            agent_id=self.agent_id,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        if self.store:
            self.store.put(entry)
        return entry

    def add_tool_call(self, tool_name: str, args: dict[str, Any], result: dict[str, Any]) -> MemoryEntry:
        entry = MemoryEntry(
            key=f"session:{self.session_id}:tool:{tool_name}:{len(self._entries)}",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.TOOL_CALL,
            value={"tool": tool_name, "args": args, "result": result},
            agent_id=self.agent_id,
        )
        self._entries.append(entry)
        if self.store:
            self.store.put(entry)
        return entry

    def get_recent(self, limit: int = 20) -> list[MemoryEntry]:
        return self._entries[-limit:]

    def flush(self) -> None:
        logger.debug("Flushing session memory", extra={"session_id": self.session_id, "count": len(self._entries)})
