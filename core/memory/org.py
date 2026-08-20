"""Organizational memory adapter for THINK BOX AI."""

from __future__ import annotations

from typing import Any

from core.foundation.logging import get_logger
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer

logger = get_logger(__name__)


class OrganizationalMemoryAdapter:
    def __init__(self, store: Any) -> None:
        self.store = store
        self._patterns: list[dict[str, Any]] = []

    def add_pattern(self, pattern: dict[str, Any]) -> MemoryEntry:
        self._patterns.append(pattern)
        entry = MemoryEntry(
            key=f"org:pattern:{len(self._patterns)}",
            layer=MemoryLayer.ORGANIZATIONAL,
            entry_type=MemoryEntryType.PATTERN,
            value=pattern,
        )
        if self.store:
            self.store.put(entry)
        return entry

    def get_patterns(self, pattern_type: str | None = None) -> list[dict[str, Any]]:
        if pattern_type is None:
            return list(self._patterns)
        return [p for p in self._patterns if p.get("pattern_type") == pattern_type]

    def flush(self) -> None:
        logger.debug("Flushing organizational memory", extra={"pattern_count": len(self._patterns)})
