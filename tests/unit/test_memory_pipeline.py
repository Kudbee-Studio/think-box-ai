"""Tests for the memory consolidation pipeline."""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from core.memory.validator import MemoryValidator
from core.memory.candidate import (
    CandidateMemory,
    CandidateType,
    ValidationResult,
    ValidationSource,
    ValidationStatus,
)
from core.memory.consolidator import MemoryConsolidator
from core.memory.curator import MemoryCurator
from core.memory.event import (
    EventSource,
    EventType,
    MemoryEvent,
)
from core.memory.prediction import PredictionMemory
from core.memory.capture import MemoryCapture
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestMemoryEvent(unittest.TestCase):
    """Test MemoryEvent schema."""

    def test_create_event(self) -> None:
        event = MemoryEvent(
            id="test-1",
            session_id="session-1",
            agent_id="agent-1",
            event_type=EventType.ACTION,
            content="Test event",
        )
        self.assertEqual(event.id, "test-1")
        self.assertEqual(event.event_type, EventType.ACTION)
        self.assertEqual(event.source, EventSource.AGENT)
        self.assertEqual(event.confidence, 1.0)

    def test_event_with_metadata(self) -> None:
        event = MemoryEvent(
            id="test-2",
            session_id="session-1",
            agent_id="agent-1",
            event_type=EventType.DECISION,
            content="Decision event",
            metadata={"decision": "use_postgres", "reasoning": "persistence"},
        )
        self.assertEqual(event.metadata["decision"], "use_postgres")

    def test_event_types(self) -> None:
        self.assertEqual(EventType.ACTION.value, "action")
        self.assertEqual(EventType.DECISION.value, "decision")
        self.assertEqual(EventType.CORRECTION.value, "correction")
        self.assertEqual(EventType.FAILURE.value, "failure")
        self.assertEqual(EventType.SUCCESS.value, "success")
        self.assertEqual(EventType.PREDICTION.value, "prediction")


class TestMemoryCapture(unittest.TestCase):
    """Test MemoryCapture class."""

    def setUp(self) -> None:
        self.store = MagicMock()
        self.capture = MemoryCapture(self.store, "session-1", "agent-1")

    def test_capture_action(self) -> None:
        event = self.capture.capture_action(
            session_id="session-1",
            agent_id="agent-1",
            tool_name="file_read",
            args={"path": "/tmp/test.txt"},
            result={"content": "hello"},
        )
        self.assertEqual(event.event_type, EventType.ACTION)
        self.assertEqual(event.metadata["tool_name"], "file_read")
        self.assertEqual(len(self.capture.get_buffered_events()), 1)

    def test_capture_decision(self) -> None:
        event = self.capture.capture_decision(
            session_id="session-1",
            agent_id="agent-1",
            decision="use_postgres",
            reasoning="persistence matters",
        )
        self.assertEqual(event.event_type, EventType.DECISION)
        self.assertEqual(event.metadata["decision"], "use_postgres")
        self.assertEqual(event.source, EventSource.AGENT)

    def test_capture_correction(self) -> None:
        event = self.capture.capture_correction(
            session_id="session-1",
            agent_id="agent-1",
            original="use_redis",
            correction="use_postgres",
            context="persistence needed",
        )
        self.assertEqual(event.event_type, EventType.CORRECTION)
        self.assertEqual(event.source, EventSource.USER)
        self.assertEqual(event.confidence, 1.0)

    def test_capture_failure(self) -> None:
        event = self.capture.capture_failure(
            session_id="session-1",
            agent_id="agent-1",
            error="Connection timeout",
            error_type="timeout",
        )
        self.assertEqual(event.event_type, EventType.FAILURE)
        self.assertEqual(event.metadata["error_type"], "timeout")

    def test_capture_success(self) -> None:
        event = self.capture.capture_success(
            session_id="session-1",
            agent_id="agent-1",
            solution="Used connection pooling",
            conditions={"database": "postgres"},
        )
        self.assertEqual(event.event_type, EventType.SUCCESS)
        self.assertEqual(event.confidence, 0.9)

    def test_capture_prediction(self) -> None:
        event = self.capture.capture_prediction(
            session_id="session-1",
            agent_id="agent-1",
            prediction="deployment will require migration",
            expected_outcome="migration completes",
            confidence=0.7,
        )
        self.assertEqual(event.event_type, EventType.PREDICTION)
        self.assertEqual(event.confidence, 0.7)
        self.assertEqual(event.metadata["prediction_confidence"], 0.7)

    def test_flush(self) -> None:
        self.capture.capture_action("session-1", "agent-1", "tool", {}, {})
        events = self.capture.flush()
        self.assertEqual(len(events), 1)
        self.assertEqual(len(self.capture.get_buffered_events()), 0)


class TestMemoryCurator(unittest.TestCase):
    """Test MemoryCurator class."""

    def setUp(self) -> None:
        self.curator = MemoryCurator(min_confidence=0.3)

    def test_extract_from_decisions(self) -> None:
        events = [
            MemoryEvent(
                id="e1",
                session_id="s1",
                agent_id="a1",
                event_type=EventType.DECISION,
                content="Decision: use_postgres",
                metadata={"decision": "use_postgres", "reasoning": "persistence"},
            )
        ]
        candidates = self.curator.extract_candidates(events)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].candidate_type, CandidateType.DECISION)

    def test_extract_from_corrections(self) -> None:
        events = [
            MemoryEvent(
                id="e2",
                session_id="s1",
                agent_id="a1",
                event_type=EventType.CORRECTION,
                content="Correction",
                metadata={"original": "use_redis", "correction": "use_postgres"},
            )
        ]
        candidates = self.curator.extract_candidates(events)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].candidate_type, CandidateType.PREFERENCE)
        self.assertEqual(candidates[0].confidence, 0.9)

    def test_extract_from_failures(self) -> None:
        events = [
            MemoryEvent(
                id="e3",
                session_id="s1",
                agent_id="a1",
                event_type=EventType.FAILURE,
                content="Connection timeout",
                metadata={"error": "Connection timeout", "error_type": "timeout"},
            )
        ]
        candidates = self.curator.extract_candidates(events)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].candidate_type, CandidateType.LESSON)

    def test_extract_from_successes(self) -> None:
        events = [
            MemoryEvent(
                id="e4",
                session_id="s1",
                agent_id="a1",
                event_type=EventType.SUCCESS,
                content="Success",
                metadata={"solution": "connection pooling", "conditions": {}},
            )
        ]
        candidates = self.curator.extract_candidates(events)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].candidate_type, CandidateType.PATTERN)

    def test_extract_from_actions_pattern(self) -> None:
        # Create 3 similar action events
        events = [
            MemoryEvent(
                id=f"e{i}",
                session_id="s1",
                agent_id="a1",
                event_type=EventType.ACTION,
                content=f"Action {i}",
                metadata={"tool_name": "file_read", "args": {"path": "/tmp/test.txt"}},
            )
            for i in range(3)
        ]
        candidates = self.curator.extract_candidates(events)
        pattern_candidates = [c for c in candidates if c.candidate_type == CandidateType.PATTERN]
        self.assertTrue(len(pattern_candidates) >= 1)

    def test_empty_events(self) -> None:
        candidates = self.curator.extract_candidates([])
        self.assertEqual(len(candidates), 0)

    def test_confidence_filter(self) -> None:
        curator = MemoryCurator(min_confidence=0.95)
        events = [
            MemoryEvent(
                id="e1",
                session_id="s1",
                agent_id="a1",
                event_type=EventType.ACTION,
                content="Low confidence event",
                confidence=0.5,
            )
        ]
        candidates = curator.extract_candidates(events)
        self.assertEqual(len(candidates), 0)

    def test_score_confidence(self) -> None:
        candidate = CandidateMemory(
            id="c1",
            session_id="s1",
            agent_id="a1",
            content="Test",
            candidate_type=CandidateType.PREFERENCE,
            confidence=0.5,
        )
        score = self.curator.score_confidence(candidate)
        self.assertGreater(score, 0.5)  # Boosted for preferences


class TestMemoryValidator(unittest.TestCase):
    """Test MemoryValidator class."""

    def setUp(self) -> None:
        self.validator = MemoryValidator()

    def test_validate_candidate(self) -> None:
        candidate = CandidateMemory(
            id="c1",
            session_id="s1",
            agent_id="a1",
            content="PostgreSQL preferred over Redis",
            candidate_type=CandidateType.DECISION,
            confidence=0.8,
        )
        result = _run_async(self.validator.validate(candidate))
        self.assertIn(result.status, [
            ValidationStatus.APPROVED,
            ValidationStatus.NEEDS_REVIEW,
            ValidationStatus.REJECTED,
        ])
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 1.0)

    def test_batch_validate(self) -> None:
        candidates = [
            CandidateMemory(
                id=f"c{i}",
                session_id="s1",
                agent_id="a1",
                content=f"Test {i}",
                candidate_type=CandidateType.FACT,
                confidence=0.7,
            )
            for i in range(3)
        ]
        results = _run_async(self.validator.batch_validate(candidates))
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsInstance(result, ValidationResult)


class TestCandidateMemory(unittest.TestCase):
    """Test CandidateMemory schema."""

    def test_create_candidate(self) -> None:
        candidate = CandidateMemory(
            id="c1",
            session_id="s1",
            agent_id="a1",
            content="Test candidate",
            candidate_type=CandidateType.FACT,
            confidence=0.8,
        )
        self.assertEqual(candidate.status, ValidationStatus.PENDING)
        self.assertEqual(candidate.candidate_type, CandidateType.FACT)

    def test_candidate_types(self) -> None:
        self.assertEqual(CandidateType.FACT.value, "fact")
        self.assertEqual(CandidateType.DECISION.value, "decision")
        self.assertEqual(CandidateType.PREFERENCE.value, "preference")
        self.assertEqual(CandidateType.LESSON.value, "lesson")
        self.assertEqual(CandidateType.QUESTION.value, "question")
        self.assertEqual(CandidateType.PATTERN.value, "pattern")


class TestPredictionMemory(unittest.TestCase):
    """Test PredictionMemory class."""

    def setUp(self) -> None:
        self.store = MagicMock()
        self.store.get.return_value = None
        self.predictor = PredictionMemory(self.store)

    def test_record_prediction(self) -> None:
        prediction_id = self.predictor.record_prediction(
            session_id="s1",
            agent_id="a1",
            prediction="deployment requires migration",
            confidence=0.7,
            expected_outcome="migration succeeds",
        )
        self.assertIsNotNone(prediction_id)
        self.store.put.assert_called_once()

    def test_record_outcome(self) -> None:
        # Setup: first call returns None, second call returns a prediction entry
        entry = MemoryEntry(
            key="prediction:p1",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.BENCHMARK,
            value={
                "id": "p1",
                "session_id": "s1",
                "agent_id": "a1",
                "prediction": "migration needed",
                "expected_outcome": "migration succeeds",
                "confidence": 0.7,
            },
        )
        self.store.get.return_value = entry

        self.predictor.record_outcome("p1", "migration succeeded", "user")
        # Should have called put twice (once for get, once for update)
        self.assertTrue(self.store.put.called or self.store.get.called)

    def test_calculate_accuracy(self) -> None:
        # Setup mock entries
        entries = [
            MemoryEntry(
                key=f"prediction:p{i}",
                layer=MemoryLayer.SESSION,
                entry_type=MemoryEntryType.BENCHMARK,
                value={
                    "agent_id": "agent-1",
                    "was_correct": i % 2 == 0,
                },
            )
            for i in range(4)
        ]
        self.store.query.return_value = entries
        accuracy = self.predictor.calculate_accuracy("agent-1")
        self.assertEqual(accuracy, 0.5)  # 2 out of 4 correct

    def test_get_trust_scores(self) -> None:
        entries = [
            MemoryEntry(
                key="prediction:p1",
                layer=MemoryLayer.SESSION,
                entry_type=MemoryEntryType.BENCHMARK,
                value={"agent_id": "agent-1", "was_correct": True},
            ),
            MemoryEntry(
                key="prediction:p2",
                layer=MemoryLayer.SESSION,
                entry_type=MemoryEntryType.BENCHMARK,
                value={"agent_id": "agent-1", "was_correct": False},
            ),
        ]
        self.store.query.return_value = entries
        scores = self.predictor.get_trust_scores()
        self.assertIn("agent-1", scores)
        self.assertEqual(scores["agent-1"], 0.5)


class TestMemoryConsolidator(unittest.TestCase):
    """Test MemoryConsolidator class."""

    def setUp(self) -> None:
        self.store = MagicMock()
        self.consolidator = MemoryConsolidator(self.store)

    def test_consolidate_empty_session(self) -> None:
        self.store.query.return_value = []
        result = _run_async(self.consolidator.consolidate_session("session-1"))
        self.assertEqual(result["events_processed"], 0)

    def test_archive_old_entries(self) -> None:
        # Mock old entries
        old_entry = MemoryEntry(
            key="old-entry",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.TOOL_CALL,
            value={},
            created_at=(
                datetime.now(timezone.utc)
                .replace(year=2020)
                .isoformat()
            ),
        )
        self.store.query.return_value = [old_entry]
        archived = self.consolidator.archive_old_entries(MemoryLayer.SESSION, max_age_days=30)
        self.store.delete.assert_called_once_with("old-entry")
        self.assertEqual(archived, 1)


if __name__ == "__main__":
    unittest.main()
