"""Memory entry schemas for THINK BOX AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MemoryLayer(str, Enum):
    SESSION = "session"
    TASK = "task"
    ORGANIZATIONAL = "organizational"
    VERIFIED_KNOWLEDGE = "verified_knowledge"


class MemoryEntryType(str, Enum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REASONING_STEP = "reasoning_step"
    GOAL_STATE = "goal_state"
    ERROR = "error"
    PATTERN = "pattern"
    FACT = "fact"
    BENCHMARK = "benchmark"


@dataclass
class MemoryEntry:
    """A single entry in the memory store."""

    key: str
    layer: MemoryLayer
    entry_type: MemoryEntryType
    value: dict[str, Any]
    agent_id: str = ""
    task_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class SessionMemory:
    """In-memory session state."""

    session_id: str
    agent_id: str
    goal_tree: dict[str, Any] = field(default_factory=dict)
    recent_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    recent_observations: list[dict[str, Any]] = field(default_factory=list)
    current_think_box_id: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TaskMemory:
    """In-memory task state."""

    task_id: str
    root_goal_id: str
    agent_id: str
    step_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    validation_outcomes: dict[str, bool] = field(default_factory=dict)
    replan_history: list[dict[str, Any]] = field(default_factory=list)
    error_log: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    status: str = "running"


@dataclass
class OrganizationalPattern:
    """A verified pattern extracted from completed tasks."""

    pattern_id: str
    pattern_type: str
    description: str
    conditions: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_verified_at: str | None = None
