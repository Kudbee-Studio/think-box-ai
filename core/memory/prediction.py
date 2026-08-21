"""Prediction memory for THINK BOX AI.

This module implements prediction tracking, allowing agents to record
predictions with confidence scores and later verify them against actual
outcomes. This creates a feedback loop that improves agent accuracy and
enables trust scoring.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from core.foundation.logging import get_logger

logger = get_logger(__name__)


class PredictionMemory:
    """Tracks agent predictions and outcomes.

    Every agent should be able to say:
        "This deployment will require database migration."
        Confidence: 70%
        Expected outcome: Migration completed without rollback.

    Then later:
        TRUE / FALSE

    The system learns:
    - where it predicts correctly
    - where it overestimates
    - which agents are reliable

    This becomes the foundation for agent trust scoring in Phase 3.

    Usage:
        predictor = PredictionMemory(store)
        prediction_id = predictor.record_prediction(
            session_id, agent_id, "deployment requires migration", 0.7, "migration succeeds"
        )
        predictor.record_outcome(prediction_id, True)
        accuracy = predictor.calculate_accuracy(agent_id)
    """

    def __init__(self, store: Any) -> None:
        """Initialize the Prediction Memory system.

        Args:
            store: Memory store for persisting predictions
        """
        self.store = store

    def record_prediction(
        self,
        session_id: str,
        agent_id: str,
        prediction: str,
        confidence: float,
        expected_outcome: str,
    ) -> str:
        """Record a new prediction.

        Args:
            session_id: Session identifier
            agent_id: Agent making the prediction
            prediction: The prediction text
            confidence: Confidence in the prediction (0.0-1.0)
            expected_outcome: What the agent expects to happen

        Returns:
            Prediction ID for later outcome recording
        """
        prediction_id = str(uuid.uuid4())
        entry: dict[str, Any] = {
            "id": prediction_id,
            "session_id": session_id,
            "agent_id": agent_id,
            "prediction": prediction,
            "confidence": confidence,
            "expected_outcome": expected_outcome,
            "actual_outcome": None,
            "outcome_timestamp": None,
            "was_correct": None,
            "feedback_source": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Store in memory store with prediction layer
        key = f"prediction:{prediction_id}"
        if self.store:
            try:
                from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer

                memory_entry = MemoryEntry(
                    key=key,
                    layer=MemoryLayer.SESSION,
                    entry_type=MemoryEntryType.BENCHMARK,
                    value=entry,
                    agent_id=agent_id,
                    metadata={"prediction_id": prediction_id},
                )
                self.store.put(memory_entry)
            except Exception as e:
                logger.warning("Failed to store prediction", extra={"error": str(e)})

        logger.info(
            "Recorded prediction",
            extra={
                "prediction_id": prediction_id,
                "agent_id": agent_id,
                "confidence": confidence,
            },
        )
        return prediction_id

    def record_outcome(
        self,
        prediction_id: str,
        actual_outcome: str,
        feedback_source: str = "user",
    ) -> None:
        """Record the actual outcome of a prediction.

        Args:
            prediction_id: ID of the prediction to update
            actual_outcome: What actually happened
            feedback_source: Who/what provided the feedback (user, test, automated)
        """
        key = f"prediction:{prediction_id}"
        entry = self.store.get(key) if self.store else None

        if entry is None:
            logger.warning("Prediction not found", extra={"prediction_id": prediction_id})
            return

        value = entry.value
        expected_outcome = value.get("expected_outcome", "")
        prediction = value.get("prediction", "")

        # Determine if prediction was correct
        was_correct = self._evaluate_prediction(prediction, expected_outcome, actual_outcome)

        value.update(
            {
                "actual_outcome": actual_outcome,
                "outcome_timestamp": datetime.now(timezone.utc).isoformat(),
                "was_correct": was_correct,
                "feedback_source": feedback_source,
            }
        )

        # Update in store
        if self.store:
            try:
                from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer

                updated_entry = MemoryEntry(
                    key=key,
                    layer=MemoryLayer.SESSION,
                    entry_type=MemoryEntryType.BENCHMARK,
                    value=value,
                    agent_id=value.get("agent_id", ""),
                    metadata={"prediction_id": prediction_id},
                )
                self.store.put(updated_entry)
            except Exception as e:
                logger.warning("Failed to update prediction outcome", extra={"error": str(e)})

        logger.info(
            "Recorded prediction outcome",
            extra={
                "prediction_id": prediction_id,
                "was_correct": was_correct,
                "feedback_source": feedback_source,
            },
        )

    def _evaluate_prediction(
        self, prediction: str, expected: str, actual: str
    ) -> bool:
        """Evaluate if a prediction was correct.

        Uses simple string matching. In a real implementation, this would
        use more sophisticated NLP to compare expected vs actual outcomes.
        """
        expected_lower = expected.lower().strip()
        actual_lower = actual.lower().strip()
        return expected_lower in actual_lower or actual_lower in expected_lower

    def calculate_accuracy(self, agent_id: str) -> float:
        """Calculate prediction accuracy for an agent.

        Args:
            agent_id: Agent to calculate accuracy for

        Returns:
            Accuracy score (0.0-1.0)
        """
        if not self.store:
            return 0.0

        try:
            from core.memory.schema import MemoryEntryType, MemoryLayer

            entries = self.store.query(
                layer=MemoryLayer.SESSION,
                entry_type=MemoryEntryType.BENCHMARK,
            )
        except Exception:
            return 0.0

        predictions = [
            e for e in entries
            if e.value.get("agent_id") == agent_id and e.value.get("was_correct") is not None
        ]

        if not predictions:
            return 0.0

        correct = sum(1 for p in predictions if p.value.get("was_correct") is True)
        return correct / len(predictions)

    def get_trust_scores(self) -> dict[str, float]:
        """Calculate trust scores for all agents.

        Returns:
            Dict mapping agent_id to trust score (0.0-1.0)
        """
        if not self.store:
            return {}

        try:
            from core.memory.schema import MemoryEntryType, MemoryLayer

            entries = self.store.query(
                layer=MemoryLayer.SESSION,
                entry_type=MemoryEntryType.BENCHMARK,
            )
        except Exception:
            return {}

        agent_predictions: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            agent_id = entry.value.get("agent_id")
            if agent_id and entry.value.get("was_correct") is not None:
                agent_predictions.setdefault(agent_id, []).append(entry.value)

        trust_scores = {}
        for agent_id, predictions in agent_predictions.items():
            correct = sum(1 for p in predictions if p.get("was_correct") is True)
            trust_scores[agent_id] = correct / len(predictions) if predictions else 0.0

        return trust_scores

    def get_prediction_history(
        self, agent_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get prediction history, optionally filtered by agent.

        Args:
            agent_id: Optional agent ID filter
            limit: Maximum number of predictions to return

        Returns:
            List of prediction records
        """
        if not self.store:
            return []

        try:
            from core.memory.schema import MemoryEntryType, MemoryLayer

            entries = self.store.query(
                layer=MemoryLayer.SESSION,
                entry_type=MemoryEntryType.BENCHMARK,
            )
        except Exception:
            return []

        predictions = []
        for entry in entries:
            value = entry.value
            if agent_id is None or value.get("agent_id") == agent_id:
                predictions.append(value)

        # Sort by created_at descending
        predictions.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return predictions[:limit]
