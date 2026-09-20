"""Stress suite: failure injection, crash-resume, idempotency, concurrency, guards."""

from __future__ import annotations

import tempfile
import unittest
from thinkbox.pr_lifecycle import (
    PRLifecycleConfig,
    PRLifecycleOrchestrator,
    PRLifecycleState,
)
from thinkbox.pr_lifecycle_resilience import (
    BOUNDARY_STAGES,
    RECOVERY_MATRIX,
    ResilienceConfig,
    ResilientPRLifecycleRunner,
    classify_four_state,
    inject_failure_matrix_report,
    run_parallel_lifecycles,
)


def _happy_base(pr_number: int = 9104) -> PRLifecycleConfig:
    return PRLifecycleConfig(
        pr_number=pr_number,
        branch="feat/pr-lifecycle-stress-resilience",
        test_mode=True,
        approvals={"merge": True},
    )


class TestRecoveryMatrix(unittest.TestCase):
    def test_all_boundaries_have_policy(self) -> None:
        for stage in BOUNDARY_STAGES:
            self.assertIn(stage, RECOVERY_MATRIX)

    def test_approval_not_retryable(self) -> None:
        p = RECOVERY_MATRIX["APPLY_APPROVAL_BOUNDARY"]
        self.assertFalse(p.retryable)
        self.assertEqual(p.exhausted_terminal, "BLOCKED")
        self.assertTrue(p.human_escalation)

    def test_inject_failure_matrix_report_shape(self) -> None:
        rows = inject_failure_matrix_report()
        self.assertEqual(len(rows), len(BOUNDARY_STAGES))
        self.assertIn("max_retries", rows[0])


class TestFailureInjectionBoundaries(unittest.TestCase):
    """Each inject_failure_at boundary → FAILED + receipt evidence."""

    def test_injected_failures_per_boundary(self) -> None:
        for stage in BOUNDARY_STAGES:
            if stage == "IDENTIFY":
                inject_at = "PR_CREATED"
            else:
                inject_at = stage
            cfg = _happy_base(pr_number=9200 + BOUNDARY_STAGES.index(stage))
            cfg.inject_failure_at = inject_at
            if stage in ("APPLY_APPROVAL_BOUNDARY", "REPLAY", "CLEANUP", "GENERATE_PROOF", "GENERATE_NEXT_ACTION", "ANALYZE"):
                cfg.approvals = {"merge": True}
            result = PRLifecycleOrchestrator(cfg).run()
            self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)
            self.assertTrue(result.receipts)
            last = result.receipts[-1]
            self.assertIn("error", last.get("evidence", {}))


class TestTransientRetryRecovery(unittest.TestCase):
    def test_transient_provision_recovers(self) -> None:
        r_cfg = ResilienceConfig(
            base=_happy_base(),
            transient_failures={"PROVISION_PERSISTENCE": 1},
            checkpoint_dir=tempfile.mkdtemp(),
        )
        runner = ResilientPRLifecycleRunner(r_cfg)
        result = runner.run_to_completion()
        self.assertEqual(result.terminal_state, PRLifecycleState.LEARN.value)
        self.assertGreaterEqual(runner.resilience_scorecard.retries_attempted, 1)

    def test_transient_exhaustion_fails_closed(self) -> None:
        r_cfg = ResilienceConfig(
            base=_happy_base(pr_number=9301),
            transient_failures={"EXECUTE": 5},
            checkpoint_dir=tempfile.mkdtemp(),
        )
        runner = ResilientPRLifecycleRunner(r_cfg)
        result = runner.run_to_completion()
        self.assertEqual(result.terminal_state, PRLifecycleState.FAILED.value)
        self.assertGreater(runner.resilience_scorecard.retries_exhausted, 0)


class TestCrashResume(unittest.TestCase):
    def test_fresh_process_resumes_without_duplicate_experiment(self) -> None:
        ck = tempfile.mkdtemp()
        base = _happy_base(pr_number=9401)
        r_cfg = ResilienceConfig(base=base, checkpoint_dir=ck)
        runner = ResilientPRLifecycleRunner(r_cfg)
        run_id = runner.orchestrator.run_id
        steps = 0
        experiment_id = None
        while not runner.orchestrator.current_state in (
            PRLifecycleState.LEARN.value,
            PRLifecycleState.FAILED.value,
            PRLifecycleState.BLOCKED.value,
        ):
            runner.step_resilient()
            steps += 1
            if runner.orchestrator.context.get("experiment_id") and experiment_id is None:
                experiment_id = runner.orchestrator.context["experiment_id"]
            if steps >= 8:
                break

        self.assertIsNotNone(experiment_id)
        resumed = ResilientPRLifecycleRunner.resume_from_checkpoint(r_cfg, run_id)
        self.assertEqual(resumed.orchestrator.context.get("experiment_id"), experiment_id)
        result = resumed.continue_after_crash()
        self.assertEqual(result.terminal_state, PRLifecycleState.LEARN.value)
        self.assertEqual(
            len([e for e in result.context.get("experiment_id", "")]),
            len(experiment_id),
        )


class TestIdempotency(unittest.TestCase):
    def test_double_provision_context_skips_second_db(self) -> None:
        cfg = _happy_base(pr_number=9501)
        orch = PRLifecycleOrchestrator(cfg)
        while orch.current_state != PRLifecycleState.PROVISION_PERSISTENCE.value:
            orch.step()
        orch.step()
        db_id = orch.context["db_id"]
        snap = orch.snapshot()
        snap["state"] = PRLifecycleState.PROVISION_PERSISTENCE.value
        orch.restore_snapshot(snap)
        orch.step()
        self.assertEqual(orch.context["db_id"], db_id)
        actions = [r.action for r in orch.receipts]
        self.assertIn("provision_persistence_idempotent", actions)

    def test_health_check_idempotent(self) -> None:
        cfg = _happy_base(pr_number=9502)
        orch = PRLifecycleOrchestrator(cfg)
        while orch.current_state != PRLifecycleState.HEALTH_CHECK.value:
            orch.step()
        orch.step()
        orch._rehydrate_runtime()
        h1 = orch._provisioner.health_check(orch.context["db_id"])
        h2 = orch._provisioner.health_check(orch.context["db_id"])
        self.assertEqual(h1["healthy"], h2["healthy"])

    def test_cleanup_idempotent(self) -> None:
        cfg = _happy_base(pr_number=9503)
        result = PRLifecycleOrchestrator(cfg).run()
        self.assertGreaterEqual(result.scorecard["cleanup_idempotent_calls"], 1)


class TestConcurrencyIsolation(unittest.TestCase):
    def test_parallel_distinct_pr_numbers(self) -> None:
        configs = [
            ResilienceConfig(
                base=_happy_base(pr_number=9600 + i),
                checkpoint_dir=tempfile.mkdtemp(),
            )
            for i in range(3)
        ]
        results = run_parallel_lifecycles(configs, max_workers=3)
        self.assertEqual(len(results), 3)
        prs = {r.pr_number for r in results}
        self.assertEqual(len(prs), 3)
        for r in results:
            self.assertEqual(r.terminal_state, PRLifecycleState.LEARN.value)


class TestSafetyGuards(unittest.TestCase):
    def test_max_steps_blocks(self) -> None:
        r_cfg = ResilienceConfig(
            base=_happy_base(pr_number=9701),
            max_total_steps=2,
            checkpoint_dir=tempfile.mkdtemp(),
        )
        runner = ResilientPRLifecycleRunner(r_cfg)
        result = runner.run_to_completion()
        self.assertEqual(result.terminal_state, PRLifecycleState.BLOCKED.value)
        self.assertIn("max_total_steps", result.error or "")

    def test_approval_denied_blocks_without_retry_storm(self) -> None:
        base = _happy_base(pr_number=9702)
        base.approvals = {}
        r_cfg = ResilienceConfig(base=base, checkpoint_dir=tempfile.mkdtemp())
        result = ResilientPRLifecycleRunner(r_cfg).run_to_completion()
        self.assertEqual(result.terminal_state, PRLifecycleState.BLOCKED.value)


class TestAuditAndScorecard(unittest.TestCase):
    def test_audit_fields_on_resilient_run(self) -> None:
        r_cfg = ResilienceConfig(base=_happy_base(pr_number=9801), checkpoint_dir=tempfile.mkdtemp())
        runner = ResilientPRLifecycleRunner(r_cfg)
        result = runner.run_to_completion()
        self.assertGreater(len(runner.audit_log), 0)
        row = runner.audit_log[0]
        self.assertIn("initiator", row)
        self.assertIn("why", row)
        self.assertIn("evidence", row)
        self.assertIn("delta", row)
        self.assertIn("next", row)
        self.assertNotIn("autonomy_score", result.scorecard)
        self.assertIn("resilience", result.scorecard)

    def test_four_state_not_production_ready_locally(self) -> None:
        v = classify_four_state(True, "LIVE_BLOCKED: no external provider")
        self.assertTrue(v.code_complete)
        self.assertTrue(v.test_verified)
        self.assertFalse(v.live_verified)
        self.assertFalse(v.production_ready)


class TestResilientHappyPath(unittest.TestCase):
    def test_full_resilient_learn(self) -> None:
        r_cfg = ResilienceConfig(base=_happy_base(pr_number=9901), checkpoint_dir=tempfile.mkdtemp())
        result = ResilientPRLifecycleRunner(r_cfg).run_to_completion()
        self.assertEqual(result.terminal_state, PRLifecycleState.LEARN.value)
        self.assertGreater(result.scorecard["checkpoints_written"] if "checkpoints_written" in result.scorecard else result.scorecard.get("resilience", {}).get("checkpoints_written", 0), 0)


if __name__ == "__main__":
    unittest.main()
