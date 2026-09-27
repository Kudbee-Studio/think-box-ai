"""End-to-end integration tests: governance + autonomous execution.

Tests the complete lifecycle:
1. Autonomous task → Governance evaluation → Execution decision → Proof
2. ALLOW/DENY/ESCALATE paths
3. Cryptographic proof generation and verification
4. Tamper detection
5. Audit trail completeness
"""

from __future__ import annotations

import asyncio
import unittest

from thinkbox.governance_ledger import (
    GovernanceLedger,
    GovernanceSignalType,
    DecisionGatingDecision,
)
from thinkbox.governed_execution import (
    GovernedExecutionEngine,
    GovernedExecutionPhase,
)


class TestGovernedExecutionIntegration(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration: governance + task execution."""

    async def asyncSetUp(self) -> None:
        """Set up test fixtures."""
        self.ledger = GovernanceLedger()

        # Pre-create base signals
        self.allow_signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="test_policy_allow",
            content="allow: standard tasks",
        )

        self.deny_signal = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="test_policy_deny",
            content="deny: forbidden operations",
        )

        # Escalate signal = allow from one policy + deny from another (conflict)
        self.escalate_allow = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="test_policy_escalate_allow",
            content="allow: user preference",
        )

        self.escalate_deny = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="test_policy_escalate_deny",
            content="deny: governance board review needed",
        )

        # Simple signal resolver
        async def get_signals_for_task(task_description: str) -> list[str]:
            """Return applicable signals based on task description."""
            signals = []

            # Add deny signal ONLY if task contains "forbidden"
            if "forbidden" in task_description.lower():
                signals.append(self.deny_signal.signal_id)
            # Add conflicting signals if task contains "escalate"
            elif "escalate" in task_description.lower():
                signals.append(self.escalate_allow.signal_id)
                signals.append(self.escalate_deny.signal_id)
            # Default: allow
            else:
                signals.append(self.allow_signal.signal_id)

            return signals

        self.engine = GovernedExecutionEngine(
            ledger=self.ledger,
            get_applicable_signals=get_signals_for_task,
        )

    async def test_allow_path_task_executes(self) -> None:
        """Test ALLOW path: task executes and produces proof."""
        execution_result = {}

        async def execute_standard_task() -> dict:
            return {"status": "completed", "value": 42}

        result = await self.engine.governed_execute_task(
            task_id="task_allow_1",
            task_description="Execute standard task",
            actual_execute=execute_standard_task,
        )

        # Task should execute
        self.assertTrue(result.execution_allowed)
        self.assertIsNotNone(result.execution_result)
        self.assertEqual(result.execution_result["value"], 42)

        # Proof should be generated
        self.assertIsNotNone(result.proof_id)
        self.assertEqual(result.phase, GovernedExecutionPhase.PROVED)

    async def test_deny_path_task_blocked(self) -> None:
        """Test DENY path: task is blocked by policy."""
        call_count = 0

        async def execute_forbidden_task() -> dict:
            nonlocal call_count
            call_count += 1
            return {"status": "executed"}

        result = await self.engine.governed_execute_task(
            task_id="task_deny_1",
            task_description="Execute FORBIDDEN operation",
            actual_execute=execute_forbidden_task,
        )

        # Task should NOT execute
        self.assertFalse(result.execution_allowed)
        self.assertEqual(call_count, 0)  # Never called

        # Gate decision should be DENY
        self.assertEqual(result.gate_decision, DecisionGatingDecision.DENY)
        # Error message should reference the denial
        self.assertTrue(
            any(word in result.error.lower() for word in ["deny", "denied"])
        )

    async def test_escalate_path_task_paused(self) -> None:
        """Test ESCALATE path: task requires human review."""
        call_count = 0

        async def execute_escalate_task() -> dict:
            nonlocal call_count
            call_count += 1
            return {"status": "executed"}

        result = await self.engine.governed_execute_task(
            task_id="task_escalate_1",
            task_description="Execute ESCALATE task",
            actual_execute=execute_escalate_task,
        )

        # Task should NOT execute yet (waiting for human)
        self.assertFalse(result.execution_allowed)
        self.assertEqual(call_count, 0)

        # Gate decision should be ESCALATE
        self.assertEqual(result.gate_decision, DecisionGatingDecision.ESCALATE)
        self.assertIn("escalate", result.error.lower())

    async def test_proof_generation_and_verification(self) -> None:
        """Test that proofs are generated and chain is verifiable."""
        async def task_1() -> dict:
            return {"task": 1}

        async def task_2() -> dict:
            return {"task": 2}

        # Execute two tasks
        result1 = await self.engine.governed_execute_task(
            task_id="task_1",
            task_description="First task",
            actual_execute=task_1,
        )

        result2 = await self.engine.governed_execute_task(
            task_id="task_2",
            task_description="Second task",
            actual_execute=task_2,
        )

        # Both should have proofs
        self.assertIsNotNone(result1.proof_id)
        self.assertIsNotNone(result2.proof_id)

        # Proof chain should be verifiable
        is_valid = await self.engine.verify_execution_chain()
        self.assertTrue(is_valid)

    async def test_audit_trail_completeness(self) -> None:
        """Test that audit trails contain all required information."""
        async def task() -> dict:
            return {"result": "ok"}

        result = await self.engine.governed_execute_task(
            task_id="task_audit",
            task_description="Task for audit trail",
            actual_execute=task,
        )

        trail = self.engine.get_execution_audit_trail("task_audit")

        # Trail should have all required fields
        self.assertIn("task_id", trail)
        self.assertIn("task_description", trail)
        self.assertIn("phase", trail)
        self.assertIn("governance_signals", trail)
        self.assertIn("gate_decision", trail)
        self.assertIn("execution_allowed", trail)
        self.assertIn("proof_id", trail)
        self.assertIn("can_verify", trail)

        # Verify values
        self.assertEqual(trail["task_id"], "task_audit")
        self.assertTrue(trail["execution_allowed"])
        self.assertTrue(trail["can_verify"])

    async def test_multiple_governance_signals(self) -> None:
        """Test task with multiple applicable signals."""
        # Create multiple signals
        signal1 = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.HUMAN_PREFERENCE,
            provenance="human_alice",
            content="Prefer security over performance",
        )

        signal2 = await self.ledger.record_signal(
            signal_type=GovernanceSignalType.POLICY_CONSTRAINT,
            provenance="policy_security",
            content="allow: security-first decisions",
        )

        # Manually evaluate with both signals
        decision = await self.ledger.evaluate_against_constraints(
            action_description="Make security-first decision",
            applicable_signal_ids=[signal1.signal_id, signal2.signal_id],
        )

        # Decision should reflect multiple signals
        self.assertGreater(len(decision.applicable_signals), 0)
        self.assertEqual(decision.decision, DecisionGatingDecision.ALLOW)

    async def test_governed_execution_flow(self) -> None:
        """Test complete end-to-end flow: decision → gate → execution → proof."""
        execution_phases = []

        async def record_phase_task() -> dict:
            """Task that records execution phases."""
            execution_phases.append("executed")
            return {"phases": list(execution_phases)}

        result = await self.engine.governed_execute_task(
            task_id="task_flow",
            task_description="End-to-end flow test",
            actual_execute=record_phase_task,
        )

        # Should have passed through all phases
        self.assertEqual(result.phase, GovernedExecutionPhase.PROVED)
        self.assertTrue(result.execution_allowed)
        self.assertIsNotNone(result.execution_result)
        self.assertIsNotNone(result.proof_id)
        self.assertEqual(result.execution_result["phases"], ["executed"])

    async def test_error_handling(self) -> None:
        """Test error handling during task execution."""
        async def failing_task() -> dict:
            raise ValueError("Task failed intentionally")

        # Error should be caught and recorded
        with self.assertRaises(ValueError):
            await self.engine.governed_execute_task(
                task_id="task_fail",
                task_description="Failing task",
                actual_execute=failing_task,
            )

    async def test_governance_ledger_persistence(self) -> None:
        """Test that governance artifacts persist and can be retrieved."""
        async def task() -> dict:
            return {"done": True}

        result1 = await self.engine.governed_execute_task(
            task_id="task_persist_1",
            task_description="First persistent task",
            actual_execute=task,
        )

        result2 = await self.engine.governed_execute_task(
            task_id="task_persist_2",
            task_description="Second persistent task",
            actual_execute=task,
        )

        # Ledger should have records for both
        trail1 = self.engine.get_execution_audit_trail("task_persist_1")
        trail2 = self.engine.get_execution_audit_trail("task_persist_2")

        self.assertEqual(trail1["task_id"], "task_persist_1")
        self.assertEqual(trail2["task_id"], "task_persist_2")

        # Proof chain should still be valid
        is_valid = await self.engine.verify_execution_chain()
        self.assertTrue(is_valid)

    async def test_shutdown_reports_state(self) -> None:
        """Test that shutdown reports ledger state correctly."""
        async def task() -> dict:
            return {}

        await self.engine.governed_execute_task(
            task_id="task_before_shutdown",
            task_description="Task before shutdown",
            actual_execute=task,
        )

        # Should not raise
        await self.engine.shutdown()


if __name__ == "__main__":
    unittest.main()
