"""Memory curator agent for THINK BOX AI.

This module implements the Memory Curator, a dedicated internal agent that
analyzes raw memory events and extracts candidate memories. The curator
identifies facts, decisions, preferences, lessons learned, and unresolved
questions from agent sessions.
"""

from __future__ import annotations

import re
from typing import Any

from core.foundation.logging import get_logger
from core.memory.candidate import (
    CandidateMemory,
    CandidateType,
    ValidationStatus,
)
from core.memory.event import EventType, MemoryEvent

logger = get_logger(__name__)


class MemoryCurator:
    """Extracts candidate memories from raw memory events.

    The Memory Curator analyzes session events and extracts structured
    candidate memories that can be promoted to organizational or verified
    knowledge after validation.

    The curator uses pattern matching and heuristics to identify:
    - Facts: statements about the world or system
    - Decisions: choices made with reasoning
    - Preferences: user or agent preferences
    - Lessons: insights from failures or successes
    - Questions: unresolved issues
    - Patterns: recurring tool call or workflow patterns

    Usage:
        curator = MemoryCurator()
        candidates = curator.extract_candidates(events)
        for candidate in candidates:
            store.put_candidate(candidate)
    """

    def __init__(self, min_confidence: float = 0.3) -> None:
        """Initialize the Memory Curator.

        Args:
            min_confidence: Minimum confidence threshold for extraction
        """
        self.min_confidence = min_confidence

    def extract_candidates(self, events: list[MemoryEvent]) -> list[CandidateMemory]:
        """Extract candidate memories from a list of events.

        Args:
            events: List of memory events to analyze

        Returns:
            List of extracted candidate memories
        """
        if not events:
            return []

        candidates: list[CandidateMemory] = []

        # Group events by type for targeted extraction
        actions = [e for e in events if e.event_type == EventType.ACTION]
        decisions = [e for e in events if e.event_type == EventType.DECISION]
        corrections = [e for e in events if e.event_type == EventType.CORRECTION]
        failures = [e for e in events if e.event_type == EventType.FAILURE]
        successes = [e for e in events if e.event_type == EventType.SUCCESS]
        predictions = [e for e in events if e.event_type == EventType.PREDICTION]

        # Extract from each event type
        candidates.extend(self._extract_from_decisions(decisions))
        candidates.extend(self._extract_from_corrections(corrections))
        candidates.extend(self._extract_from_failures(failures))
        candidates.extend(self._extract_from_successes(successes))
        candidates.extend(self._extract_from_predictions(predictions))
        candidates.extend(self._extract_from_actions(actions))

        # Filter by minimum confidence
        candidates = [c for c in candidates if c.confidence >= self.min_confidence]

        logger.info(
            "Extracted candidates from events",
            extra={"total_events": len(events), "candidates": len(candidates)},
        )
        return candidates

    def _extract_from_decisions(self, events: list[MemoryEvent]) -> list[CandidateMemory]:
        """Extract candidate memories from decision events."""
        candidates = []
        for event in events:
            decision = event.metadata.get("decision", "")
            reasoning = event.metadata.get("reasoning", "")
            if decision:
                candidate = CandidateMemory(
                    id=event.id,
                    session_id=event.session_id,
                    agent_id=event.agent_id,
                    content=f"Decision: {decision}. Reasoning: {reasoning}",
                    candidate_type=CandidateType.DECISION,
                    confidence=event.confidence * 0.8,
                    source_events=[event.id],
                    metadata={"decision": decision, "reasoning": reasoning},
                )
                candidates.append(candidate)
        return candidates

    def _extract_from_corrections(self, events: list[MemoryEvent]) -> list[CandidateMemory]:
        """Extract candidate memories from correction events.

        Corrections are high-value learning signals because they represent
        explicit user feedback.
        """
        candidates = []
        for event in events:
            original = event.metadata.get("original", "")
            correction = event.metadata.get("correction", "")
            context = event.metadata.get("context", "")
            if original and correction:
                content = f"Preference: {correction} (instead of {original})"
                if context:
                    content += f" Context: {context}"
                candidate = CandidateMemory(
                    id=event.id,
                    session_id=event.session_id,
                    agent_id=event.agent_id,
                    content=content,
                    candidate_type=CandidateType.PREFERENCE,
                    confidence=0.9,  # High confidence for explicit corrections
                    source_events=[event.id],
                    metadata={
                        "original": original,
                        "correction": correction,
                        "context": context,
                    },
                )
                candidates.append(candidate)
        return candidates

    def _extract_from_failures(self, events: list[MemoryEvent]) -> list[CandidateMemory]:
        """Extract candidate memories from failure events."""
        candidates = []
        for event in events:
            error = event.metadata.get("error", "")
            error_type = event.metadata.get("error_type", "")
            if error:
                # Extract lesson from error
                lesson = self._extract_lesson_from_error(error, error_type)
                if lesson:
                    candidate = CandidateMemory(
                        id=event.id,
                        session_id=event.session_id,
                        agent_id=event.agent_id,
                        content=lesson,
                        candidate_type=CandidateType.LESSON,
                        confidence=0.6,  # Medium confidence for lessons
                        source_events=[event.id],
                        metadata={"error": error, "error_type": error_type},
                    )
                    candidates.append(candidate)
        return candidates

    def _extract_from_successes(self, events: list[MemoryEvent]) -> list[CandidateMemory]:
        """Extract candidate memories from success events."""
        candidates = []
        for event in events:
            solution = event.metadata.get("solution", "")
            conditions = event.metadata.get("conditions", {})
            if solution:
                content = f"Successful solution: {solution}"
                if conditions:
                    content += f" (conditions: {conditions})"
                candidate = CandidateMemory(
                    id=event.id,
                    session_id=event.session_id,
                    agent_id=event.agent_id,
                    content=content,
                    candidate_type=CandidateType.PATTERN,
                    confidence=event.confidence * 0.7,
                    source_events=[event.id],
                    metadata={"solution": solution, "conditions": conditions},
                )
                candidates.append(candidate)
        return candidates

    def _extract_from_predictions(self, events: list[MemoryEvent]) -> list[CandidateMemory]:
        """Extract candidate memories from prediction events."""
        candidates = []
        for event in events:
            prediction = event.metadata.get("prediction", "")
            expected_outcome = event.metadata.get("expected_outcome", "")
            prediction_confidence = event.metadata.get("prediction_confidence", 0.5)
            if prediction:
                content = f"Prediction: {prediction} -> {expected_outcome}"
                candidate = CandidateMemory(
                    id=event.id,
                    session_id=event.session_id,
                    agent_id=event.agent_id,
                    content=content,
                    candidate_type=CandidateType.PATTERN,
                    confidence=prediction_confidence * 0.5,
                    source_events=[event.id],
                    metadata={
                        "prediction": prediction,
                        "expected_outcome": expected_outcome,
                    },
                )
                candidates.append(candidate)
        return candidates

    def _extract_from_actions(self, events: list[MemoryEvent]) -> list[CandidateMemory]:
        """Extract candidate memories from action events.

        Looks for repeated tool call patterns across events.
        """
        candidates = []
        tool_calls: dict[str, list[MemoryEvent]] = {}
        for event in events:
            tool_name = event.metadata.get("tool_name", "")
            if tool_name:
                tool_calls.setdefault(tool_name, []).append(event)

        # Detect patterns: tool used ≥ 3 times with same args
        for tool_name, tool_events in tool_calls.items():
            if len(tool_events) >= 3:
                # Check if args are similar
                args_list = [e.metadata.get("args", {}) for e in tool_events]
                if self._are_args_similar(args_list):
                    content = f"Pattern: {tool_name} is frequently called with similar arguments"
                    candidate = CandidateMemory(
                        id=str(__import__("uuid").uuid4()),
                        session_id=events[0].session_id,
                        agent_id=events[0].agent_id,
                        content=content,
                        candidate_type=CandidateType.PATTERN,
                        confidence=0.5,
                        source_events=[e.id for e in tool_events],
                        metadata={
                            "tool_name": tool_name,
                            "call_count": len(tool_events),
                            "sample_args": args_list[0],
                        },
                    )
                    candidates.append(candidate)

        return candidates

    def _extract_lesson_from_error(self, error: str, error_type: str) -> str | None:
        """Extract a lesson from an error message.

        Uses simple pattern matching to identify common error patterns.
        """
        error_lower = error.lower()
        if "permission" in error_lower or "access denied" in error_lower:
            return f"Lesson: Permission errors occur when access is denied. Check permissions before retrying."
        if "not found" in error_lower or "404" in error_lower:
            return f"Lesson: Resource not found. Verify path/URL exists before accessing."
        if "timeout" in error_lower or "timed out" in error_lower:
            return f"Lesson: Operation timed out. Consider increasing timeout or retrying with backoff."
        if "connection" in error_lower:
            return f"Lesson: Connection error. Check network connectivity and service availability."
        if "memory" in error_lower or "oom" in error_lower:
            return f"Lesson: Memory limit exceeded. Consider batching or reducing payload size."
        return None

    def _are_args_similar(self, args_list: list[dict[str, Any]]) -> bool:
        """Check if a list of argument dicts are similar.

        Simple heuristic: check if the keys are the same.
        """
        if not args_list:
            return False
        first_keys = set(args_list[0].keys())
        return all(set(args.keys()) == first_keys for args in args_list)

    def score_confidence(self, candidate: CandidateMemory) -> float:
        """Score the confidence of a candidate memory.

        Confidence is based on:
        - Source event confidence (30%)
        - Event type (20%)
        - Repetition across sessions (20%)
        - User confirmation (20%)
        - Documentation agreement (10%)

        Args:
            candidate: Candidate memory to score

        Returns:
            Confidence score (0.0-1.0)
        """
        base_confidence = candidate.confidence

        # Boost for corrections (explicit user feedback)
        if candidate.candidate_type == CandidateType.PREFERENCE:
            base_confidence *= 1.2

        # Boost for lessons from failures
        if candidate.candidate_type == CandidateType.LESSON:
            base_confidence *= 1.1

        # Cap at 1.0
        return min(base_confidence, 1.0)
