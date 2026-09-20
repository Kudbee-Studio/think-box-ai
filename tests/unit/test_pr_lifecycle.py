"""Tests for autonomous PR lifecycle orchestrator (local SQLite, no cloud)."""

from __future__ import annotations

import unittest

from thinkbox.pr_lifecycle import (
    AutonomyScorecard,
    GATED_CLOSE_ACTIONS,
    PRLifecycle,
    PRLifecycleConfig,
    PRLifecycleOrchestrator,
    PRLifecycleState,
    PR_LIFECYCLE_STATES,
)


class TestPRLifecycleTransitions(unittest.TestCase):
    def test_linear_success_chain(self) -> None:
        states = [
            "PR_CREATED",
            "IDENTIFY",
            "PROVISION_PERSISTENCE",
            "HEALTH_CHECK",
            "EXECUTE",
            "OBSERVE",
            "ANALYZE",
            "COMPARE",
            "GENERATE_PROOF",
            "GENERATE_NEXT_ACTION",
            "APPLY_APPROVAL_BOUNDARY",
            "REPLAY",
            "READY_FOR_CLOSE",
            "CLEANUP",
            "LEARN",
        ]
        for i in range(len(states) - 1):
            self.assertTrue(PRLifecycle.can_transition(states[i], states[i + 1]))

    def test_invalid_skip_transition(self) -> None:
        self.assertFalse(PRLifecycle.can_transition("PR_CREATED", "EXECUTE"))
        with self.assertRaises(ValueError):
            PRLifecycle.validate_transition("PR_CREATED", "EXECUTE")

    def test_fail_from_non_terminal(self) -> None:
        self.assertTrue(PRLifecycle.can_transition("EXECUTE", "FAILED"))

    def test_terminal_learn(self) -> None:
        self.assertTrue(PRLifecycle.is_terminal("LEARN"))
        self.assertFalse(PRLifecycle.can_transition("LEARN", "IDENTIFY"))

    def test_all_states_registered(self) -> None:
        for action in GATED_CLOSE_ACTIONS:
            self.assertIn(action, (
                "merge",
                "deploy_production",
                "infrastructure_change",
                "spend_budget",
                "delete_data",
                "modify_experiment_history",
            ))
        self.assertIn("FAILED", PR_LIFECYCLE_STATES)
        self.assertIn("BLOCKED", PR_LIFECYCLE_STATES)


class TestAutonomyScorecard(unittest.TestCase):
    def test_raw_metrics_only(self) -> None:
        card = AutonomyScorecard(
            transitions_completed=10,
            terminal_state="LEARN",
        )
        data = card.to_dict()
        self.assertNotIn("score", data)
        self.assertNotIn("autonomy_score", data)
        self.assertEqual(data["transitions_completed"], 10)


class TestPRLifecycleHappyPath(unittest.TestCase):
    def test_full_loop_learn(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            branch="feat/multi-metric-mercury-analytics",
            test_mode=True,
            approvals={"merge": True},
        )
        orch = PRLifecycleOrchestrator(config)
        result = orch.run()
        self.assertEqual(result.terminal_state, PRLifecycleState.LEARN.value)
        self.assertIsNone(result.error)
        self.assertTrue(result.scorecard["replay_performed"])
        self.assertTrue(result.scorecard["cleanup_performed"])
        self.assertEqual(result.scorecard["cleanup_idempotent_calls"], 1)
        self.assertGreater(result.scorecard["approval_gates_encountered"], 0)
        self.assertIn("experiment_id", result.context)
        self.assertIn("proof_sha256", result.context)

    def test_receipt_order_matches_pipeline(self) -> None:
        config = PRLifecycleConfig(pr_number=104, test_mode=True, approvals={"merge": True})
        result = PRLifecycleOrchestrator(config).run()
        to_states = [r["to_state"] for r in result.receipts]
        self.assertEqual(to_states[0], "IDENTIFY")
        self.assertIn("REPLAY", to_states)
        idx_replay = to_states.index("REPLAY")
        idx_cleanup = to_states.index("CLEANUP")
        self.assertLess(idx_replay, idx_cleanup)

    def test_deterministic_metrics(self) -> None:
        runs = [
            {
                "throughput": 5.0,
                "p50_latency": 0.1,
                "p95_latency": 0.2,
                "p99_latency": 0.3,
                "error_rate": 0.0,
                "iteration_count": 1,
            },
            {
                "throughput": 6.0,
                "p50_latency": 0.11,
                "p95_latency": 0.21,
                "p99_latency": 0.31,
                "error_rate": 0.0,
                "iteration_count": 2,
            },
        ]
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            approvals={"merge": True},
            deterministic_metrics=runs,
        )
        r1 = PRLifecycleOrchestrator(config).run()
        r2 = PRLifecycleOrchestrator(config).run()
        self.assertEqual(r1.context.get("metrics_summary"), r2.context.get("metrics_summary"))


class TestPRLifecycleFailures(unittest.TestCase):
    def test_fail_provision(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=False,
            inject_failure_at=None,
        )
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"UPSTASH_API_KEY": ""}, clear=True):
            result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)
        self.assertIn("BLOCKED", result.error or result.receipts[-1]["evidence"].get("error", ""))

    def test_fail_injected_execute(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            inject_failure_at="EXECUTE",
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)

    def test_fail_injected_analyze(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            approvals={"merge": True},
            inject_failure_at="ANALYZE",
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)

    def test_fail_injected_proof(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            approvals={"merge": True},
            inject_failure_at="GENERATE_PROOF",
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)

    def test_fail_injected_health_check(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            inject_failure_at="HEALTH_CHECK",
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)

    def test_fail_injected_cleanup(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            approvals={"merge": True},
            inject_failure_at="CLEANUP",
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)

    def test_fail_injected_replay(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            approvals={"merge": True},
            inject_failure_at="REPLAY",
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)

    def test_fail_compare_insufficient_runs(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            approvals={"merge": True},
            deterministic_metrics=[
                {
                    "throughput": 1.0,
                    "p50_latency": 0.1,
                    "p95_latency": 0.2,
                    "p99_latency": 0.3,
                    "error_rate": 0.0,
                    "iteration_count": 1,
                }
            ],
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)


class TestPRLifecycleApproval(unittest.TestCase):
    def test_approval_denied_blocks(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            approvals={"merge": False},
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.BLOCKED.value)
        self.assertGreater(result.scorecard["approval_denied_count"], 0)

    def test_approval_required_missing_blocks(self) -> None:
        config = PRLifecycleConfig(pr_number=104, test_mode=True, approvals={})
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.BLOCKED.value)

    def test_gated_actions_never_bypassed(self) -> None:
        from thinkbox.experiment_analytics import ApprovalBoundary
        from thinkbox.experiment import ExperimentManager
        import tempfile
        import os

        tmp = tempfile.mkdtemp()
        mgr = ExperimentManager(db_path=os.path.join(tmp, "e.db"))
        boundary = ApprovalBoundary(mgr)
        for action in GATED_CLOSE_ACTIONS:
            self.assertTrue(boundary.requires_approval(action))


class TestPRLifecycleReplayAndCleanup(unittest.TestCase):
    def test_replay_before_cleanup_receipts(self) -> None:
        config = PRLifecycleConfig(pr_number=104, test_mode=True, approvals={"merge": True})
        result = PRLifecycleOrchestrator(config).run()
        actions = [r["action"] for r in result.receipts]
        self.assertIn("replay_from_evidence", actions)
        self.assertIn("cleanup", actions)

    def test_skip_cleanup_then_manual_cleanup(self) -> None:
        config = PRLifecycleConfig(
            pr_number=104,
            test_mode=True,
            approvals={"merge": True},
            skip_cleanup=True,
        )
        result = PRLifecycleOrchestrator(config).run()
        self.assertEqual(result.terminal_state, PRLifecycleState.LEARN.value)
        self.assertFalse(result.scorecard["cleanup_performed"])
        self.assertIn("cleanup_skipped", [r["action"] for r in result.receipts])

    def test_cleanup_idempotent_via_happy_path(self) -> None:
        config = PRLifecycleConfig(pr_number=104, test_mode=True, approvals={"merge": True})
        result = PRLifecycleOrchestrator(config).run()
        self.assertGreaterEqual(result.scorecard["cleanup_idempotent_calls"], 1)


class TestPRLifecycleOrchestratorGuards(unittest.TestCase):
    def test_step_after_terminal_raises(self) -> None:
        config = PRLifecycleConfig(pr_number=104, test_mode=True, approvals={"merge": True})
        orch = PRLifecycleOrchestrator(config)
        orch.run()
        with self.assertRaises(RuntimeError):
            orch.step()

    def test_identity_preserved_on_receipts(self) -> None:
        config = PRLifecycleConfig(pr_number=104, branch="feat/test", test_mode=True, approvals={"merge": True})
        result = PRLifecycleOrchestrator(config).run()
        for receipt in result.receipts:
            self.assertEqual(receipt["pr_number"], 104)
            self.assertEqual(receipt["branch"], "feat/test")
            self.assertEqual(receipt["run_id"], result.run_id)


if __name__ == "__main__":
    unittest.main()
