"""Tests for Autonomous Alignment & Governance Layer.

Tests for AI safety innovation: continuous value learning, alignment verification,
and cryptographic proof of ethical reasoning.
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from thinkbox.autonomous_alignment_governance import (
    AlignmentSignal,
    AutonomousAlignmentGovernance,
    ValueDimension,
    ValueSignal,
    AutonomousDecision,
)


class TestValueModel(unittest.IsolatedAsyncioTestCase):
    """Test value learning and model updates."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.governance = AutonomousAlignmentGovernance()

    async def test_default_values(self) -> None:
        """Test default human values are initialized."""
        model = self.governance._value_model

        self.assertGreater(model.dimensions[ValueDimension.SAFETY], 0.9)
        self.assertGreater(model.dimensions[ValueDimension.TRANSPARENCY], 0.8)
        self.assertGreater(model.dimensions[ValueDimension.BENEFICENCE], 0.7)

    async def test_value_dimensions_exist(self) -> None:
        """Test all value dimensions are represented."""
        for dimension in ValueDimension:
            self.assertIn(dimension, self.governance._value_model.dimensions)
            self.assertIn(dimension, self.governance._value_model.confidence_scores)


class TestAlignmentEvaluation(unittest.IsolatedAsyncioTestCase):
    """Test alignment scoring and decision evaluation."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.governance = AutonomousAlignmentGovernance(
            alignment_threshold=0.75,
            drift_threshold=0.2,
        )

    async def test_evaluate_aligned_decision(self) -> None:
        """Test evaluation of a well-aligned decision."""
        decision = await self.governance.evaluate_decision(
            action="Help vulnerable population",
            reasoning="This action maximizes human benefit",
            value_scores={
                ValueDimension.BENEFICENCE: 0.9,
                ValueDimension.JUSTICE: 0.8,
                ValueDimension.TRANSPARENCY: 0.85,
            },
        )

        self.assertTrue(decision.is_approved)
        self.assertGreater(decision.alignment_score, 0.75)

    async def test_evaluate_misaligned_decision(self) -> None:
        """Test evaluation of a misaligned decision."""
        decision = await self.governance.evaluate_decision(
            action="Prioritize profit over people",
            reasoning="This action maximizes short-term gain",
            value_scores={
                ValueDimension.BENEFICENCE: -0.8,
                ValueDimension.JUSTICE: -0.7,
                ValueDimension.TRANSPARENCY: 0.2,
            },
        )

        self.assertFalse(decision.is_approved)
        self.assertLess(decision.alignment_score, 0.75)

    async def test_decision_requires_escalation_on_drift(self) -> None:
        """Test that decisions with high drift require escalation."""
        decision = await self.governance.evaluate_decision(
            action="Unusual decision",
            reasoning="Breaking from pattern",
            value_scores={
                ValueDimension.BENEFICENCE: -0.5,  # High drift
                ValueDimension.SAFETY: 0.2,  # High drift
            },
        )

        self.assertTrue(decision.requires_escalation)

    async def test_alignment_proof_generated(self) -> None:
        """Test that alignment proofs are generated."""
        decision = await self.governance.evaluate_decision(
            action="Test action",
            reasoning="Test reasoning",
            value_scores={
                ValueDimension.BENEFICENCE: 0.8,
                ValueDimension.SAFETY: 0.9,
            },
        )

        self.assertIsNotNone(decision.proof)
        self.assertIsNotNone(decision.proof.reasoning_hash)
        self.assertIsNotNone(decision.proof.value_model_hash)


class TestValueLearning(unittest.IsolatedAsyncioTestCase):
    """Test learning from human feedback."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.governance = AutonomousAlignmentGovernance()

    async def test_learn_from_approval_feedback(self) -> None:
        """Test learning when human approves a decision."""
        decision = await self.governance.evaluate_decision(
            action="Help others",
            reasoning="Maximize beneficence",
            value_scores={
                ValueDimension.BENEFICENCE: 0.9,
                ValueDimension.JUSTICE: 0.8,
            },
        )

        initial_beneficence = self.governance._value_model.dimensions[ValueDimension.BENEFICENCE]

        await self.governance.learn_from_feedback(
            decision_id=decision.decision_id,
            signal=AlignmentSignal.APPROVE,
            feedback_values={
                ValueDimension.BENEFICENCE: 0.95,
                ValueDimension.JUSTICE: 0.85,
            },
            confidence=0.9,
        )

        # Value model should shift toward approved values
        new_beneficence = self.governance._value_model.dimensions[ValueDimension.BENEFICENCE]
        self.assertGreater(new_beneficence, initial_beneficence)

    async def test_learn_from_rejection_feedback(self) -> None:
        """Test learning when human rejects a decision."""
        decision = await self.governance.evaluate_decision(
            action="Ignore fairness",
            reasoning="Focus on efficiency",
            value_scores={
                ValueDimension.JUSTICE: -0.7,
            },
        )

        initial_justice = self.governance._value_model.dimensions[ValueDimension.JUSTICE]

        await self.governance.learn_from_feedback(
            decision_id=decision.decision_id,
            signal=AlignmentSignal.REJECT,
            feedback_values={
                ValueDimension.JUSTICE: 0.9,
            },
            confidence=0.95,
        )

        # Value model should shift toward higher justice after rejection
        new_justice = self.governance._value_model.dimensions[ValueDimension.JUSTICE]
        self.assertGreater(new_justice, initial_justice)

    async def test_confidence_increases_with_feedback(self) -> None:
        """Test that confidence in learned values increases."""
        initial_confidence = self.governance._value_model.confidence_scores[
            ValueDimension.BENEFICENCE
        ]

        for _ in range(5):
            await self.governance.learn_from_feedback(
                decision_id=f"decision_{_}",
                signal=AlignmentSignal.APPROVE,
                feedback_values={
                    ValueDimension.BENEFICENCE: 0.85,
                },
                confidence=0.8,
            )

        new_confidence = self.governance._value_model.confidence_scores[
            ValueDimension.BENEFICENCE
        ]
        self.assertGreater(new_confidence, initial_confidence)


class TestProofChain(unittest.IsolatedAsyncioTestCase):
    """Test cryptographic proof chain for auditability."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.governance = AutonomousAlignmentGovernance()

    async def test_proof_chain_created(self) -> None:
        """Test that proof chain is created for decisions."""
        decision1 = await self.governance.evaluate_decision(
            action="Action 1",
            reasoning="Reasoning 1",
            value_scores={ValueDimension.BENEFICENCE: 0.8},
        )

        decision2 = await self.governance.evaluate_decision(
            action="Action 2",
            reasoning="Reasoning 2",
            value_scores={ValueDimension.BENEFICENCE: 0.8},
        )

        self.assertEqual(len(self.governance._proof_chain), 2)

    async def test_proof_chain_valid(self) -> None:
        """Test proof chain verification."""
        for i in range(3):
            await self.governance.evaluate_decision(
                action=f"Action {i}",
                reasoning=f"Reasoning {i}",
                value_scores={ValueDimension.BENEFICENCE: 0.8},
            )

        is_valid = self.governance.verify_proof_chain()
        self.assertTrue(is_valid)

    async def test_proof_contains_hashes(self) -> None:
        """Test that proofs contain cryptographic hashes."""
        decision = await self.governance.evaluate_decision(
            action="Test action",
            reasoning="Test reasoning chain",
            value_scores={ValueDimension.BENEFICENCE: 0.8},
        )

        proof = decision.proof
        self.assertIsNotNone(proof.reasoning_hash)
        self.assertIsNotNone(proof.value_model_hash)
        # Hashes should be 64 chars (SHA256)
        self.assertEqual(len(proof.reasoning_hash), 64)
        self.assertEqual(len(proof.value_model_hash), 64)


class TestAlignmentReport(unittest.IsolatedAsyncioTestCase):
    """Test alignment reporting and transparency."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.governance = AutonomousAlignmentGovernance()

    async def test_alignment_report_generated(self) -> None:
        """Test that comprehensive alignment report is generated."""
        # Create some decisions
        for i in range(5):
            await self.governance.evaluate_decision(
                action=f"Action {i}",
                reasoning=f"Reasoning {i}",
                value_scores={
                    ValueDimension.BENEFICENCE: 0.8,
                    ValueDimension.SAFETY: 0.9,
                },
            )

        report = self.governance.get_alignment_report()

        self.assertIn("total_decisions", report)
        self.assertIn("approved_decisions", report)
        self.assertIn("average_alignment_score", report)
        self.assertIn("proof_chain_valid", report)
        self.assertEqual(report["total_decisions"], 5)

    async def test_report_shows_learned_values(self) -> None:
        """Test that report reflects learned values."""
        # Learn some preferences
        for _ in range(3):
            decision = await self.governance.evaluate_decision(
                action="Test",
                reasoning="Test",
                value_scores={ValueDimension.TRANSPARENCY: 0.95},
            )

            await self.governance.learn_from_feedback(
                decision_id=decision.decision_id,
                signal=AlignmentSignal.APPROVE,
                feedback_values={ValueDimension.TRANSPARENCY: 0.98},
                confidence=0.9,
            )

        report = self.governance.get_alignment_report()
        self.assertGreater(report["value_model"][ValueDimension.TRANSPARENCY.value], 0.8)

    async def test_report_detects_drift(self) -> None:
        """Test that report detects value drift."""
        # Create a highly drifting decision
        await self.governance.evaluate_decision(
            action="Completely different",
            reasoning="Breaking all norms",
            value_scores={
                ValueDimension.SAFETY: -0.9,
                ValueDimension.BENEFICENCE: -0.8,
            },
        )

        report = self.governance.get_alignment_report()
        # Should flag drift even if auto-approved
        self.assertGreater(report["drift_score"], 0)


if __name__ == "__main__":
    unittest.main()
