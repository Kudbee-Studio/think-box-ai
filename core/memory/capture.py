"""Memory event capture for THINK BOX AI.

This module provides the MemoryCapture class that instruments agent execution
to capture all meaningful events: actions, decisions, corrections, failures,
successes, and predictions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from core.foundation.logging import get_logger
from core.memory.event import (
    EventSource,
    EventType,
    MemoryEvent,
)

logger = get_logger(__name__)


class MemoryCapture:
    """Captures memory events during agent execution.

    This class provides methods to capture all types of memory events.
    Events are stored with embeddings for semantic search.

    Usage:
        capture = MemoryCapture(store, session_id, agent_id)
        capture.capture_action(session_id, agent_id, "file_read", {"path": "x"}, result)
        capture.capture_decision(session_id, agent_id, "use_postgres", "persistence")
    """

    def __init__(self, store: Any, session_id: str, agent_id: str) -> None:
        self.store = store
        self.session_id = session_id
        self.agent_id = agent_id
        self._event_buffer: list[MemoryEvent] = []

    def _create_event(
        self,
        event_type: EventType,
        content: str,
        source: EventSource = EventSource.AGENT,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEvent:
        """Create a new memory event."""
        event_id = str(uuid.uuid4())
        event = MemoryEvent(
            id=event_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            source=source,
            content=content,
            confidence=confidence,
            metadata=metadata or {},
        )
        self._event_buffer.append(event)
        return event

    def capture_action(
        self,
        session_id: str,
        agent_id: str,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        duration_ms: float | None = None,
    ) -> MemoryEvent:
        """Capture an agent action (tool call).

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            tool_name: Name of the tool called
            args: Arguments passed to the tool
            result: Result returned by the tool
            duration_ms: Optional execution duration in milliseconds

        Returns:
            MemoryEvent capturing this action
        """
        content = f"Called {tool_name} with args {args}"
        metadata = {
            "tool_name": tool_name,
            "args": args,
            "result": result,
            "duration_ms": duration_ms,
        }
        event = self._create_event(
            event_type=EventType.ACTION,
            content=content,
            source=EventSource.AGENT,
            confidence=1.0,
            metadata=metadata,
        )
        logger.debug("Captured action event", extra={"event_id": event.id, "tool": tool_name})
        return event

    def capture_decision(
        self,
        session_id: str,
        agent_id: str,
        decision: str,
        reasoning: str,
        alternatives: list[str] | None = None,
    ) -> MemoryEvent:
        """Capture an agent decision.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            decision: The decision made
            reasoning: Why this decision was made
            alternatives: Other options considered

        Returns:
            MemoryEvent capturing this decision
        """
        content = f"Decision: {decision}. Reasoning: {reasoning}"
        metadata = {
            "decision": decision,
            "reasoning": reasoning,
            "alternatives": alternatives or [],
        }
        event = self._create_event(
            event_type=EventType.DECISION,
            content=content,
            source=EventSource.AGENT,
            confidence=0.8,
            metadata=metadata,
        )
        logger.debug("Captured decision event", extra={"event_id": event.id, "decision": decision})
        return event

    def capture_correction(
        self,
        session_id: str,
        agent_id: str,
        original: str,
        correction: str,
        context: str = "",
    ) -> MemoryEvent:
        """Capture a user correction.

        User corrections are high-value learning signals.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            original: What the agent did/said originally
            correction: What the user corrected it to
            context: Additional context for the correction

        Returns:
            MemoryEvent capturing this correction
        """
        content = f"Correction: '{original}' -> '{correction}'. Context: {context}"
        metadata = {
            "original": original,
            "correction": correction,
            "context": context,
        }
        event = self._create_event(
            event_type=EventType.CORRECTION,
            content=content,
            source=EventSource.USER,
            confidence=1.0,
            metadata=metadata,
        )
        logger.debug("Captured correction event", extra={"event_id": event.id})
        return event

    def capture_failure(
        self,
        session_id: str,
        agent_id: str,
        error: str,
        error_type: str = "",
        context: dict[str, Any] | None = None,
        recovery_attempted: bool = False,
    ) -> MemoryEvent:
        """Capture a failure.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            error: Error message or description
            error_type: Type/category of error
            context: Additional context (tool args, stack trace, etc.)
            recovery_attempted: Whether recovery was attempted

        Returns:
            MemoryEvent capturing this failure
        """
        content = f"Failure: {error}"
        metadata = {
            "error": error,
            "error_type": error_type,
            "context": context or {},
            "recovery_attempted": recovery_attempted,
        }
        event = self._create_event(
            event_type=EventType.FAILURE,
            content=content,
            source=EventSource.AGENT,
            confidence=1.0,
            metadata=metadata,
        )
        logger.debug("Captured failure event", extra={"event_id": event.id, "error_type": error_type})
        return event

    def capture_success(
        self,
        session_id: str,
        agent_id: str,
        solution: str,
        conditions: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> MemoryEvent:
        """Capture a successful solution.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            solution: Description of the solution
            conditions: Conditions under which this solution works
            metrics: Performance metrics (time, tokens, etc.)

        Returns:
            MemoryEvent capturing this success
        """
        content = f"Success: {solution}"
        metadata = {
            "solution": solution,
            "conditions": conditions or {},
            "metrics": metrics or {},
        }
        event = self._create_event(
            event_type=EventType.SUCCESS,
            content=content,
            source=EventSource.AGENT,
            confidence=0.9,
            metadata=metadata,
        )
        logger.debug("Captured success event", extra={"event_id": event.id})
        return event

    def capture_prediction(
        self,
        session_id: str,
        agent_id: str,
        prediction: str,
        expected_outcome: str,
        confidence: float = 0.5,
    ) -> MemoryEvent:
        """Capture an agent prediction.

        Predictions are later verified against actual outcomes to
        improve agent accuracy and trust scoring.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            prediction: What the agent predicts will happen
            expected_outcome: The expected result
            confidence: Confidence in the prediction (0.0-1.0)

        Returns:
            MemoryEvent capturing this prediction
        """
        content = f"Prediction: {prediction} (confidence: {confidence:.0%})"
        metadata = {
            "prediction": prediction,
            "expected_outcome": expected_outcome,
            "prediction_confidence": confidence,
        }
        event = self._create_event(
            event_type=EventType.PREDICTION,
            content=content,
            source=EventSource.AGENT,
            confidence=confidence,
            metadata=metadata,
        )
        logger.debug("Captured prediction event", extra={"event_id": event.id, "confidence": confidence})
        return event

    def flush(self) -> list[MemoryEvent]:
        """Flush buffered events to the store.

        Returns:
            List of events that were flushed
        """
        events = list(self._event_buffer)
        self._event_buffer.clear()
        return events

    def get_buffered_events(self) -> list[MemoryEvent]:
        """Get currently buffered events without flushing.

        Returns:
            List of buffered events
        """
        return list(self._event_buffer)
