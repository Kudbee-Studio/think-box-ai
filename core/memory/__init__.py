"""Memory subsystem for THINK BOX AI.

Provides multi-layered memory with consolidation pipeline:

- core.memory.schema — Base schemas (MemoryEntry, MemoryLayer, etc.)
- core.memory.store — SQLite-backed memory store
- core.memory.session — Session memory adapter
- core.memory.task — Task memory adapter
- core.memory.org — Organizational memory adapter
- core.memory.event — Memory event schema and types
- core.memory.capture — Event capture during agent execution
- core.memory.candidate — Candidate memory and validation schemas
- core.memory.curator — Memory Curator agent for extraction
- core.memory.validator — Verification pipeline
- core.memory.prediction — Prediction memory and trust scoring
- core.memory.consolidator — Memory consolidation pipeline
"""

from core.memory.candidate import (
    CandidateMemory,
    CandidateType,
    ValidationResult,
    ValidationSource,
    ValidationStatus,
)
from core.memory.capture import MemoryCapture
from core.memory.consolidator import MemoryConsolidator
from core.memory.curator import MemoryCurator
from core.memory.event import (
    EventSource,
    EventType,
    MemoryEvent,
)
from core.memory.prediction import PredictionMemory
from core.memory.schema import (
    MemoryEntry,
    MemoryEntryType,
    MemoryLayer,
    OrganizationalPattern,
    SessionMemory,
    TaskMemory,
)
from core.memory.store import MemoryStore

__all__ = [
    "CandidateMemory",
    "CandidateType",
    "EventSource",
    "EventType",
    "MemoryCapture",
    "MemoryConsolidator",
    "MemoryCurator",
    "MemoryEntry",
    "MemoryEntryType",
    "MemoryEvent",
    "MemoryLayer",
    "MemoryStore",
    "MemoryValidator",
    "OrganizationalPattern",
    "PredictionMemory",
    "SessionMemory",
    "TaskMemory",
    "ValidationResult",
    "ValidationSource",
    "ValidationStatus",
]
