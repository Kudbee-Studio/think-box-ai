"""Memory event schema for THINK BOX AI.

This module defines the event types and schemas for the memory event capture system.
Events are the raw material for the memory consolidation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Types of memory events that can be captured."""

    ACTION = "action"
    DECISION = "decision"
    CORRECTION = "correction"
    FAILURE = "failure"
    SUCCESS = "success"
    PREDICTION = "prediction"


class EventSource(str, Enum):
    """Source of a memory event."""

    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


@dataclass
class MemoryEvent:
    """A raw memory event captured during agent execution.

    Events are the atomic units of experience. They are captured
    automatically and fed into the Memory Curator for extraction.

    Attributes:
        id: Unique event identifier
        session_id: Session this event belongs to
        agent_id: Agent that generated or received this event
        timestamp: When the event occurred
        event_type: Type of event (action, decision, correction, etc.)
        source: Who/what generated this event
        content: Human-readable description of the event
        embedding: Vector embedding of the content (set by capture service)
        confidence: Confidence in this event's accuracy (0.0-1.0)
        metadata: Additional structured data (tool args, error codes, etc.)
    """

    id: str
    session_id: str
    agent_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: EventType = EventType.ACTION
    source: EventSource = EventSource.AGENT
    content: str = ""
    embedding: list[float] | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionEvent:
    """Event for agent actions (tool calls)."""

    tool_name: str
    args: dict[str, Any]
    result: dict[str, Any]
    duration_ms: float | None = None


@dataclass
class DecisionEvent:
    """Event for agent decisions."""

    decision: str
    reasoning: str
    alternatives: list[str] = field(default_factory=list)


@dataclass
class CorrectionEvent:
    """Event for user corrections."""

    original: str
    correction: str
    context: str = ""


@dataclass
class FailureEvent:
    """Event for failures."""

    error: str
    error_type: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False


@dataclass
class SuccessEvent:
    """Event for successful solutions."""

    solution: str
    conditions: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionEvent:
    """Event for agent predictions."""

    prediction: str
    expected_outcome: str
    confidence: float = 0.5
