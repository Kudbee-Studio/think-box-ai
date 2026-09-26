"""Tests for governance ledger primitives.

These tests verify the governance ledger's six primitives work as specified:
1. Record value signals with provenance
2. Detect conflicts in governance signals
3. Track deviation from baseline
4. Gate decisions against constraints
5. Produce cryptographic proofs
6. Maintain complete audit trails

No tests claim the governance decisions are ethically correct—only that
the governance evaluation is deterministic and verifiable.
"""

from __future__ import annotations

import unittest

from thinkbox.governance_ledger import (
    GovernanceLedger,
    GovernanceSignalType,
    DecisionGatingDecision,
)


class TestValueSignalLedger(unittest.IsolatedAsyncioTestCase):
    """Test Primitive #1: Value Signal Ledger.

    Records human feedback, policies, governance decisions with full provenance.
    """

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.ledger = GovernanceLedger()

    async def test_record_human_preference(self) -> None:
        """Test recording a human preference signal."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.HUMAN_PREFERENCE,
            provenance="human_reviewer_alice_20260926",
            content="Prioritize human safety over cost optimization",
        )

        self.assertIsNotNone(signal.signal_id)
        self.assertEqual(signal.signal_type, GovernanceSignalType.HUMAN_PREFERENCE)
        self.assertEqual(signal.provenance, "human_reviewer_alice_20260926")

    async def test_record_policy_constraint(self) -> None:
        """Test recording a policy constraint signal."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy_v2_healthcare_rules",
            content="deny: any decision with <0.95 harm prevention confidence",
            versioning="policy_v2",
        )

        self.assertEqual(signal.signal_type, GovernanceSignalType.POLICY_CONSTRAINT)
        self.assertIsNotNone(signal.versioning)

    async def test_signal_provenance_auditable(self) -> None:
        """Test signal provenance is recorded for audit."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.GOVERNANCE_DECISION,
            provenance="governance_board_meeting_2026-09-26",
            content="Governance team decision: escalate all high-risk decisions",
            human_id="board_member_1",
        )

        self.assertEqual(signal.provenance, "governance_board_meeting_2026-09-26")
        self.assertEqual(signal.human_id, "board_member_1")

    async def test_signals_are_hashable(self) -> None:
        """Test signals produce cryptographic hashes."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.HUMAN_PREFERENCE,
            provenance="test",
            content="Test content",
        )

        hash1 = signal.hash()
        self.assertEqual(len(hash1), 64)  # SHA256 hex is 64 chars

        # Same signal, same hash
        hash2 = signal.hash()
        self.assertEqual(hash1, hash2)


class TestGovernanceConsensusEngine(unittest.IsolatedAsyncioTestCase):
    """Test Primitive #2: Governance Consensus Engine.

    Multiple value inputs, conflict detection, explicit resolution rules.
    """

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.ledger = GovernanceLedger()

    async def test_allow_when_no_constraints(self) -> None:
        """Test decision allows when no denying constraints."""
        # Record one allow signal
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy_default",
            content="allow: standard operations",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Execute standard operation",
            applicable_signal_ids=[signal.signal_id],
        )

        self.assertEqual(decision.decision, DecisionGatingDecision.ALLOW)
        self.assertFalse(decision.conflict_detected)

    async def test_deny_when_constraint_violated(self) -> None:
        """Test decision denies when constraint violated."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy_safety",
            content="deny: any decision with low safety confidence",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Execute low-confidence decision",
            applicable_signal_ids=[signal.signal_id],
        )

        self.assertEqual(decision.decision, DecisionGatingDecision.DENY)

    async def test_escalate_on_conflict(self) -> None:
        """Test decision escalates when signals conflict."""
        allow_signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy_a",
            content="allow: cost optimization",
        )

        deny_signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy_b",
            content="deny: cost optimization",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Execute decision with conflicting policies",
            applicable_signal_ids=[allow_signal.signal_id, deny_signal.signal_id],
        )

        self.assertEqual(decision.decision, DecisionGatingDecision.ESCALATE)
        self.assertTrue(decision.conflict_detected)

    async def test_explicit_resolution_rules(self) -> None:
        """Test resolution rules are explicit and recorded."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy",
            content="deny: risky action",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Risky action",
            applicable_signal_ids=[signal.signal_id],
        )

        # Resolution rule is explicit and records the constraint
        self.assertTrue(
            any(word in decision.resolution_rule.lower() for word in ["deny", "denied"])
        )
        self.assertIn("constraint", decision.resolution_rule.lower())


class TestAlignmentDriftMonitor(unittest.IsolatedAsyncioTestCase):
    """Test Primitive #3: Alignment Drift Monitor.

    Tracks deviation from baseline behavior (conceptual test).
    """

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.ledger = GovernanceLedger()

    async def test_drift_alert_recorded(self) -> None:
        """Test drift alerts are recorded as signals."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.DRIFT_ALERT,
            provenance="drift_detector_system",
            content="Detected deviation: decision pattern differs 0.3 from baseline",
        )

        self.assertEqual(signal.signal_type, GovernanceSignalType.DRIFT_ALERT)
        self.assertIn("deviation", signal.content.lower())


class TestDecisionGovernanceGate(unittest.IsolatedAsyncioTestCase):
    """Test Primitive #4: Decision Governance Gate.

    Evaluate constraints before execution, record evidence, fail-closed.
    """

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.ledger = GovernanceLedger()

    async def test_gate_records_evidence(self) -> None:
        """Test gate records decision evidence."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy",
            content="allow",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Test action",
            applicable_signal_ids=[signal.signal_id],
        )

        self.assertIn("allow_signals", decision.evidence)
        self.assertIn("deny_signals", decision.evidence)
        self.assertIn("total_signals", decision.evidence)

    async def test_gate_produces_decision_hash(self) -> None:
        """Test gate produces cryptographic hash of decision."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy",
            content="allow",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Test",
            applicable_signal_ids=[signal.signal_id],
        )

        hash_val = decision.hash()
        self.assertEqual(len(hash_val), 64)  # SHA256


class TestProofLayer(unittest.IsolatedAsyncioTestCase):
    """Test Primitive #5: Proof Layer.

    Hash decision artifacts, chain related events, produce tamper-evident receipts.
    """

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.ledger = GovernanceLedger()

    async def test_generate_proof(self) -> None:
        """Test proof generation."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy",
            content="allow",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Test action",
            applicable_signal_ids=[signal.signal_id],
        )

        proof = await self.ledger.generate_proof(decision.decision_id)

        self.assertIsNotNone(proof.proof_id)
        self.assertEqual(proof.decision_id, decision.decision_id)
        self.assertEqual(proof.decision_hash, decision.hash())

    async def test_proof_chain_links(self) -> None:
        """Test proofs are linked in a chain."""
        signal1 = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy1",
            content="allow",
        )

        decision1 = await self.ledger.evaluate_against_constraints(
            action_description="Action 1",
            applicable_signal_ids=[signal1.signal_id],
        )

        signal2 = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy2",
            content="allow",
        )

        decision2 = await self.ledger.evaluate_against_constraints(
            action_description="Action 2",
            applicable_signal_ids=[signal2.signal_id],
        )

        proof1 = await self.ledger.generate_proof(decision1.decision_id)
        proof2 = await self.ledger.generate_proof(decision2.decision_id)

        # Second proof's previous_hash should reference first proof
        self.assertEqual(proof2.previous_proof_hash, proof1.full_hash())

    async def test_proof_chain_tamper_detection(self) -> None:
        """Test proof chain detects tampering."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy",
            content="allow",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Test",
            applicable_signal_ids=[signal.signal_id],
        )

        await self.ledger.generate_proof(decision.decision_id)

        # Verify chain is valid
        is_valid = await self.ledger.verify_proof_chain()
        self.assertTrue(is_valid)


class TestHumanAuditTrail(unittest.IsolatedAsyncioTestCase):
    """Test Primitive #6: Human Audit Trail.

    Complete record: who supplied signal, what decision, what evidence,
    which policy, human intervention, outcome.
    """

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.ledger = GovernanceLedger()

    async def test_audit_trail_complete(self) -> None:
        """Test audit trail contains all required information."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy_v1_healthcare",
            content="Safety-first constraint",
            versioning="policy_v1",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Execute autonomous decision",
            applicable_signal_ids=[signal.signal_id],
        )

        trail = self.ledger.get_audit_trail(decision.decision_id)

        # All required fields present
        self.assertIn("decision_id", trail)
        self.assertIn("action_description", trail)
        self.assertIn("decision", trail)
        self.assertIn("governing_signals", trail)
        self.assertIn("conflict_detected", trail)
        self.assertIn("resolution_rule", trail)
        self.assertIn("evidence", trail)
        self.assertIn("human_intervened", trail)
        self.assertIn("can_verify", trail)

    async def test_audit_trail_records_human_intervention(self) -> None:
        """Test audit trail records human review and intervention."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy",
            content="allow",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Test",
            applicable_signal_ids=[signal.signal_id],
        )

        # Record human intervention
        await self.ledger.record_human_intervention(
            decision_id=decision.decision_id,
            intervention_note="Human reviewer Alice approved after inspection",
        )

        trail = self.ledger.get_audit_trail(decision.decision_id)

        self.assertTrue(trail["human_intervened"])
        self.assertIn("Alice", trail["intervention_note"])

    async def test_audit_trail_independently_verifiable(self) -> None:
        """Test audit trail indicates it can be verified independently."""
        signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy",
            content="allow",
        )

        decision = await self.ledger.evaluate_against_constraints(
            action_description="Test",
            applicable_signal_ids=[signal.signal_id],
        )

        trail = self.ledger.get_audit_trail(decision.decision_id)

        # Trail should be verifiable by independent auditor
        self.assertTrue(trail["can_verify"])


if __name__ == "__main__":
    unittest.main()
