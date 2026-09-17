"""Manufacturing knowledge memory."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class KnowledgeEntry:
    knowledge_type: str
    content: str
    source_job_id: str = ""
    confidence: float = 0.8
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def model_dump(self) -> dict[str, Any]:
        return {"knowledge_type": self.knowledge_type, "content": self.content, "source_job_id": self.source_job_id, "confidence": self.confidence, "timestamp": self.timestamp}


class ManufacturingMemory:
    def __init__(self, storage_path: str = "data/cnc/memory"):
        self.storage_path = Path(storage_path)
        self._entries: list[KnowledgeEntry] = []
        self._load()

    def _load(self) -> None:
        mem_file = self.storage_path / "manufacturing_memory.json"
        if mem_file.exists():
            try:
                data = json.loads(mem_file.read_text())
                self._entries = [KnowledgeEntry(**e) for e in data.get("entries", [])]
            except (json.JSONDecodeError, ValueError):
                self._entries = []

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        mem_file = self.storage_path / "manufacturing_memory.json"
        data = {"entries": [e.model_dump() for e in self._entries]}
        mem_file.write_text(json.dumps(data, indent=2))

    def store_knowledge(self, knowledge_type: str, content: str, source_job_id: str = "", confidence: float = 0.8) -> KnowledgeEntry:
        entry = KnowledgeEntry(knowledge_type=knowledge_type, content=content, source_job_id=source_job_id, confidence=confidence)
        self._entries.append(entry)
        self._save()
        return entry

    def recall(self, query: str) -> list[KnowledgeEntry]:
        results = []
        query_lower = query.lower()
        for entry in self._entries:
            if query_lower in entry.content.lower() or query_lower in entry.knowledge_type.lower():
                results.append(entry)
        return results

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [e.model_dump() for e in self._entries]}
