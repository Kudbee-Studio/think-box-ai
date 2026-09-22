"""Phase 1 e2e: governed runtime loop — hermetic mock provider (audit F009).

Ten major improvements over PR #126 scaffold:
  1. Shared ``hermetic_scaffold`` (harness, subtasks, mock provider router)
  2. ``asyncio.run`` helper instead of manual event-loop lifecycle
  3. Ledger chain + allowed/denied entry assertions on every path
  4. Valid token → admission → ``execute_goal`` → verified ledger
  5. Invalid / mismatched token → fail-closed denial + ledger proof
  6. Permission-denied capability (tool-style) → error handling + ledger
  7. Revoked token path after registration
  8. ``execute_verified_task`` with scripted mock completions
  9. Five-subtask Think Job loop (submit → admit → execute → proof → verify)
 10. Goal-level DAG metadata persisted on the action ledger (F023 prep)
"""

from __future__ import annotations

import json
import unittest

from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.governed import GovernedEngine, GovernedEngineConfig

from tests.e2e.hermetic_scaffold import (
    assert_ledger_chain,
    five_tool_think_job_subtasks,
    ledger_allowed_count,
    ledger_denied_count,
    make_governed,
    mock_complete_router,
    run_async,
    subtask_spec,
)


class TestGovernedAdmissionE2E(unittest.TestCase):
    """Token admission and denial paths with ledger verification."""

    def test_valid_token_admits_goal_execution_and_ledger(self) -> None:
        governed = make_governed()
        token = governed.register_agent("e2e-agent", ["goal:execute"])

        result = run_async(
            governed.execute_goal(
                "hermetic e2e goal",
                token_value=token,
                agent_id="e2e-agent",
                capability="goal:execute",
            )
        )

        self.assertTrue(result.get("governed"))
        self.assertGreaterEqual(ledger_allowed_count(governed), 1)
        assert_ledger_chain(governed)

    def test_invalid_token_denies_goal_and_records_denial(self) -> None:
        governed = make_governed()
        governed.register_agent("e2e-agent-2", ["goal:execute"])

        result = run_async(
            governed.execute_goal(
                "should not run",
                token_value="invalid-token",
                agent_id="e2e-agent-2",
                capability="goal:execute",
            )
        )

        self.assertFalse(result.get("governed", True))
        self.assertIn("reason", result)
        self.assertGreaterEqual(ledger_denied_count(governed), 1)
        assert_ledger_chain(governed)

    def test_permission_denied_tool_capability_not_granted(self) -> None:
        governed = make_governed()
        token = governed.register_agent("tool-agent", ["tool:filesystem:read"])

        decision = governed.authorize(
            token,
            "tool-agent",
            "tool:filesystem:write",
            "write_file",
            metadata={"path": "/tmp/hermetic.txt"},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "capability_not_granted")
        entries = [e for e in governed.ledger.entries() if e["action"] == "write_file"]
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0]["allowed"])
        assert_ledger_chain(governed)

    def test_revoked_token_denies_subsequent_goal(self) -> None:
        governed = make_governed()
        token = governed.register_agent("revoke-agent", ["goal:execute"])
        governed._tokens.revoke_for_agent("revoke-agent")

        result = run_async(
            governed.execute_goal(
                "after revoke",
                token_value=token,
                agent_id="revoke-agent",
                capability="goal:execute",
            )
        )

        self.assertFalse(result.get("governed", True))
        self.assertGreaterEqual(ledger_denied_count(governed), 1)
        assert_ledger_chain(governed)


class TestGovernedVerifiedTaskE2E(unittest.TestCase):
    """Mock-provider verified task primitive (no ModelProvider HTTP)."""

    def test_verified_task_mock_provider_first_try_success(self) -> None:
        governed = make_governed()

        async def complete(_prompt: str) -> str:
            return '{"answer": 5}'

        out = run_async(
            governed.execute_verified_task(
                "e2e-task-1",
                "prompt",
                lambda t: (True, "valid"),
                lambda tax: "again",
                complete,
                agent_id="e2e-verified",
                experiment_id="exp-e2e-1",
            )
        )

        self.assertEqual(out["execution_status"], "FIRST_TRY_SUCCESS")
        self.assertTrue(out["valid"])
        assert_ledger_chain(governed)

    def test_verified_task_permission_style_denial_via_budget(self) -> None:
        from thinkbox.pop_arena import VerifiedRetryConfig, VerifiedRetrySession

        governed = make_governed()
        sess = VerifiedRetrySession(VerifiedRetryConfig(max_retries=1, max_calls=1))

        async def complete(_prompt: str) -> str:
            return '{"result": 1}'

        out = run_async(
            governed.execute_verified_task(
                "e2e-task-fail",
                "prompt",
                lambda t: (False, "distractor-compliance"),
                lambda tax: "again",
                complete,
                session=sess,
                agent_id="e2e-verified",
                experiment_id="exp-e2e-fail",
            )
        )

        self.assertEqual(out["execution_status"], "BUDGET_EXHAUSTED")
        self.assertFalse(out["valid"])
        denied = [e for e in governed.ledger.entries() if not e["allowed"]]
        self.assertGreaterEqual(len(denied), 1)
        assert_ledger_chain(governed)


class TestThinkJobFiveToolHermeticE2E(unittest.TestCase):
    """Full five-subtask loop as far as architecture supports without live substrate."""

    def test_five_tool_submit_admit_execute_proof_verify(self) -> None:
        subtasks = five_tool_think_job_subtasks()
        complete, _calls = mock_complete_router(subtasks, {})
        governed = make_governed()
        token = governed.register_agent("think-job-agent", ["goal:execute"])

        summary = run_async(
            governed.execute_verified_goal(
                "hermetic think job",
                subtasks,
                complete,
                token_value=token,
                agent_id="think-job-agent",
                capability="goal:execute",
            )
        )

        verified = summary["verified"]
        self.assertTrue(summary.get("governed"))
        self.assertEqual(verified["tasks"], 5)
        self.assertEqual(verified["first_try_successes"], 5)
        self.assertEqual(verified["verification_rate"], 1.0)
        self.assertEqual(summary["successful"], 5)
        self.assertEqual(summary["failed"], 0)
        self.assertTrue(summary.get("session_id"))
        self.assertEqual(len(summary.get("task_experiment_ids", {})), 5)

        goal_entries = [
            e
            for e in governed.ledger.entries()
            if e["action"] == "execute_verified_goal" and e.get("reason") == "DAG_COMPLETE"
        ]
        self.assertEqual(len(goal_entries), 1)
        raw = governed.ledger._conn.execute(
            "SELECT metadata FROM ledger WHERE action='execute_verified_goal' AND reason='DAG_COMPLETE'"
        ).fetchone()
        self.assertIsNotNone(raw)
        meta = json.loads(raw[0])
        self.assertEqual(meta["tasks"], 5)
        self.assertEqual(meta["first_try_successes"], 5)
        assert_ledger_chain(governed)

    def test_verified_goal_denied_without_valid_token(self) -> None:
        subtasks = [subtask_spec("compute", "add_small")]
        complete, _ = mock_complete_router(subtasks, {})
        governed = make_governed()
        governed.register_agent("no-token-agent", ["goal:execute"])

        summary = run_async(
            governed.execute_verified_goal(
                "denied dag",
                subtasks,
                complete,
                token_value="not-a-real-token",
                agent_id="no-token-agent",
                capability="goal:execute",
            )
        )

        self.assertFalse(summary.get("governed", True))
        self.assertGreaterEqual(ledger_denied_count(governed), 1)
        assert_ledger_chain(governed)

    def test_single_subtask_recovery_path_still_hermetic(self) -> None:
        subtasks = [subtask_spec("distractor", "wrongkey")]
        complete, calls = mock_complete_router(subtasks, {0: "wrongkey_then_valid"})
        governed = make_governed()
        token = governed.register_agent("recovery-agent", ["goal:execute"])

        summary = run_async(
            governed.execute_verified_goal(
                "recovery job",
                subtasks,
                complete,
                token_value=token,
                agent_id="recovery-agent",
            )
        )

        self.assertEqual(summary["verified"]["recovered_successes"], 1)
        self.assertEqual(summary["verified"]["first_try_successes"], 0)
        self.assertEqual(summary["successful"], 1)
        self.assertGreaterEqual(sum(calls.values()), 2)
        assert_ledger_chain(governed)


class TestGovernedRuntimeLoopLegacyCompat(unittest.TestCase):
    """Preserve PR #126 entry points (import stability)."""

    def test_governed_goal_with_valid_token(self) -> None:
        base = ThinkBoxEngine(EngineConfig())
        governed = GovernedEngine(GovernedEngineConfig(engine=base))
        token = governed.register_agent("e2e-agent", ["goal:execute"])
        result = run_async(
            governed.execute_goal(
                "hermetic e2e goal",
                token_value=token,
                agent_id="e2e-agent",
                capability="goal:execute",
            )
        )
        self.assertTrue(result.get("governed"))
        self.assertTrue(governed.ledger.verify())

    def test_governed_goal_denied_without_token(self) -> None:
        base = ThinkBoxEngine(EngineConfig())
        governed = GovernedEngine(GovernedEngineConfig(engine=base))
        governed.register_agent("e2e-agent-2", ["goal:execute"])
        result = run_async(
            governed.execute_goal(
                "should not run",
                token_value="invalid-token",
                agent_id="e2e-agent-2",
                capability="goal:execute",
            )
        )
        self.assertFalse(result.get("governed", True))
        self.assertTrue(governed.ledger.verify())


if __name__ == "__main__":
    unittest.main()
