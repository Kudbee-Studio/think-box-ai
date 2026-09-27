"""F023 — hermetic Think Job lifecycle e2e (PR #130).

Extends PR #127 governed loop + PR #128 F023 prep with full submit → admit →
execute → proof → verify paths using ``ModelProvider`` wiring, dashboard
emission, and on-disk experiment artifacts. No live Mercury / HTTP.
"""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

from core.providers.base import ModelProvider
from thinkbox.dashboard_state import DashboardCategory, DashboardEvent
from thinkbox.experiment import ExperimentManager
from thinkbox.pop_arena import secrets_clean

from tests.e2e.hermetic_scaffold import (
    HermeticModelProvider,
    assert_hermetic_blob_has_no_secrets,
    assert_ledger_chain,
    collect_hermetic_artifact_blob,
    five_tool_think_job_subtasks,
    isolated_dashboard_state,
    ledger_denied_count,
    make_governed,
    mock_complete_router,
    provider_complete_async,
    run_async,
    run_hermetic_think_job,
    subtask_spec,
    temp_experiment_stack,
    verify_dag_proof_file,
)


class TestF023ModelProviderWiring(unittest.TestCase):
    def test_hermetic_provider_satisfies_protocol(self) -> None:
        subtasks = [subtask_spec("compute", "add_small")]
        provider: ModelProvider = HermeticModelProvider(subtasks)
        self.assertTrue(provider.capabilities.completion)

    def test_provider_bridge_invokes_complete_not_http(self) -> None:
        subtasks = [subtask_spec("compute", "add_small")]
        provider = HermeticModelProvider(subtasks)
        complete = provider_complete_async(provider)
        governed = make_governed()
        token = governed.register_agent("provider-agent", ["goal:execute"])
        summary = run_async(
            run_hermetic_think_job(
                governed,
                "provider wired",
                subtasks,
                complete,
                token_value=token,
                agent_id="provider-agent",
            )
        )
        self.assertGreaterEqual(provider.complete_calls, 1)
        self.assertEqual(summary["verified"]["first_try_successes"], 1)
        assert_ledger_chain(governed)


class TestF023FullLifecyclePersistence(unittest.TestCase):
    def test_submit_admit_execute_proof_verify_on_disk(self) -> None:
        subtasks = five_tool_think_job_subtasks()
        provider = HermeticModelProvider(subtasks)
        complete = provider_complete_async(provider)
        with temp_experiment_stack() as (mgr, db_path, art_dir):
            governed = make_governed(ledger_path=str(Path(db_path).parent / "ledger.db"))
            token = governed.register_agent("lifecycle-agent", ["goal:execute"])
            summary = run_async(
                run_hermetic_think_job(
                    governed,
                    "f023 full lifecycle",
                    subtasks,
                    complete,
                    token_value=token,
                    agent_id="lifecycle-agent",
                    manager=mgr,
                )
            )
            goal_exp = summary["goal_experiment_id"]
            proof_path = Path(summary["proof_artifact"])
            self.assertTrue(proof_path.is_file())
            verify_dag_proof_file(proof_path, summary["proof_sha256"])

            fresh = ExperimentManager(db_path=str(db_path), artifacts_dir=str(art_dir))
            goal_row = fresh.db.get_experiment(goal_exp)
            self.assertIsNotNone(goal_row)
            self.assertEqual(goal_row["status"], "completed")
            for exp_id in summary["task_experiment_ids"].values():
                self.assertIsNotNone(fresh.db.get_experiment(exp_id))

            conn = sqlite3.connect(str(db_path))
            proof_rows = conn.execute(
                "SELECT hash, evidence_label FROM proof_records WHERE experiment_id=?",
                (goal_exp,),
            ).fetchall()
            conn.close()
            self.assertEqual(len(proof_rows), 1)
            self.assertEqual(proof_rows[0][0], summary["proof_sha256"])
            self.assertEqual(proof_rows[0][1], "verified")
            assert_ledger_chain(governed)

    def test_restart_reload_preserves_session_and_parameters(self) -> None:
        subtasks = [
            subtask_spec("compute", "add_small"),
            subtask_spec("distractor", "wrongkey", depends_on=[0]),
        ]
        provider = HermeticModelProvider(subtasks, {1: "wrongkey_then_valid"})
        complete = provider_complete_async(provider)
        with temp_experiment_stack() as (mgr, db_path, art_dir):
            governed = make_governed()
            token = governed.register_agent("reload-agent", ["goal:execute"])
            summary = run_async(
                run_hermetic_think_job(
                    governed,
                    "reload",
                    subtasks,
                    complete,
                    token_value=token,
                    agent_id="reload-agent",
                    manager=mgr,
                )
            )
            session_id = summary["session_id"]
            goal_exp = summary["goal_experiment_id"]
            reloaded = ExperimentManager(db_path=str(db_path), artifacts_dir=str(art_dir))
            sess = reloaded.db.get_session(session_id)
            self.assertIsNotNone(sess)
            conn = sqlite3.connect(str(db_path))
            params = {
                (r[0], r[1]): r[2]
                for r in conn.execute(
                    "SELECT experiment_id, name, value FROM experiment_parameters"
                )
            }
            conn.close()
            self.assertEqual(params[(goal_exp, "scope")], "dag")
            self.assertEqual(params[(goal_exp, "recovered_successes")], "1")


class TestF023DashboardEmission(unittest.TestCase):
    def test_emit_dashboard_job_completed_hermetic(self) -> None:
        subtasks = [subtask_spec("compute", "add_small")]
        provider = HermeticModelProvider(subtasks)
        complete = provider_complete_async(provider)
        with isolated_dashboard_state() as dash:
            governed = make_governed()
            token = governed.register_agent("dash-agent", ["goal:execute"])
            summary = run_async(
                run_hermetic_think_job(
                    governed,
                    "dashboard job",
                    subtasks,
                    complete,
                    token_value=token,
                    agent_id="dash-agent",
                    emit_dashboard=True,
                )
            )
            self.assertTrue(summary.get("governed"))
            completed = [
                e
                for e in dash.events
                if e.category == DashboardCategory.THINK_JOBS
                and e.event_type == DashboardEvent.JOB_COMPLETED
            ]
            self.assertEqual(len(completed), 1)
            payload = completed[0].data
            self.assertEqual(payload["job_id"], summary["goal_experiment_id"])
            self.assertEqual(payload["kind"], "verified_goal_dag")
            self.assertEqual(completed[0].evidence_label, "verified")
            self.assertEqual(completed[0].source, "GovernedEngine.execute_verified_goal")


class TestF023GovernanceEdgeCases(unittest.TestCase):
    def test_revoked_token_denies_before_dag_execution(self) -> None:
        subtasks = [subtask_spec("compute", "add_small")]
        complete, _ = mock_complete_router(subtasks, {})
        governed = make_governed()
        token = governed.register_agent("revoke-f023", ["goal:execute"])
        governed._tokens.revoke_for_agent("revoke-f023")
        summary = run_async(
            run_hermetic_think_job(
                governed,
                "revoked",
                subtasks,
                complete,
                token_value=token,
                agent_id="revoke-f023",
            )
        )
        self.assertFalse(summary.get("governed", True))
        self.assertGreaterEqual(ledger_denied_count(governed), 1)
        self.assertNotIn("goal_experiment_id", summary)
        assert_ledger_chain(governed)

    def test_wrong_capability_denies_admission(self) -> None:
        subtasks = [subtask_spec("compute", "add_small")]
        complete, _ = mock_complete_router(subtasks, {})
        governed = make_governed()
        token = governed.register_agent("cap-agent", ["tool:filesystem:read"])
        summary = run_async(
            run_hermetic_think_job(
                governed,
                "wrong cap",
                subtasks,
                complete,
                token_value=token,
                agent_id="cap-agent",
                capability="goal:execute",
            )
        )
        self.assertFalse(summary.get("governed", True))
        assert_ledger_chain(governed)

    def test_budget_exhaustion_on_multi_task_dag(self) -> None:
        subtasks = [
            subtask_spec("distractor", "wrongkey"),
            subtask_spec("distractor", "apology"),
        ]
        complete, _ = mock_complete_router(subtasks, {0: "wrongkey_always", 1: "valid"})
        governed = make_governed()
        token = governed.register_agent("budget-agent", ["goal:execute"])
        summary = run_async(
            run_hermetic_think_job(
                governed,
                "budget",
                subtasks,
                complete,
                token_value=token,
                agent_id="budget-agent",
                max_calls=2,
            )
        )
        self.assertGreaterEqual(summary["verified"]["budget_exhausted"], 1)
        assert_ledger_chain(governed)

    def test_partial_dag_failure_mixed_outcomes(self) -> None:
        subtasks = [
            subtask_spec("compute", "add_small"),
            subtask_spec("distractor", "wrongkey"),
            subtask_spec("compute", "mul_small", depends_on=[0]),
        ]
        complete, _ = mock_complete_router(
            subtasks, {1: "wrongkey_then_valid", 2: "arithmetic_always"}
        )
        governed = make_governed()
        token = governed.register_agent("partial-agent", ["goal:execute"])
        summary = run_async(
            run_hermetic_think_job(
                governed,
                "partial",
                subtasks,
                complete,
                token_value=token,
                agent_id="partial-agent",
            )
        )
        v = summary["verified"]
        self.assertEqual(v["tasks"], 3)
        self.assertEqual(v["first_try_successes"], 1)
        self.assertEqual(v["recovered_successes"], 1)
        self.assertEqual(v["failures"], 1)
        self.assertIn("layers_telemetry", summary)
        assert_ledger_chain(governed)


class TestF023TelemetryIntegrity(unittest.TestCase):
    def test_session_id_stable_on_task_ledger_entries(self) -> None:
        subtasks = [subtask_spec("compute", "add_small"), subtask_spec("compute", "mul_small")]
        complete, _ = mock_complete_router(subtasks, {})
        ledger_path = ":memory:"
        governed = make_governed(ledger_path=ledger_path)
        token = governed.register_agent("sess-agent", ["goal:execute"])
        summary = run_async(
            run_hermetic_think_job(
                governed,
                "session stable",
                subtasks,
                complete,
                token_value=token,
                agent_id="sess-agent",
            )
        )
        session_id = summary["session_id"]
        rows = governed.ledger._conn.execute(
            "SELECT action, metadata FROM ledger WHERE action LIKE 'verified_task:%'"
        ).fetchall()
        self.assertGreaterEqual(len(rows), 2)
        for action, meta_json in rows:
            meta = json.loads(meta_json)
            self.assertEqual(meta["session_id"], session_id)

    def test_token_usage_from_provider_recorded(self) -> None:
        subtasks = [subtask_spec("compute", "add_carry")]
        provider = HermeticModelProvider(subtasks, {0: "valid_with_usage"})
        complete = provider_complete_async(provider)
        with temp_experiment_stack() as (mgr, db_path, art_dir):
            governed = make_governed(ledger_path=str(Path(db_path).parent / "led.db"))
            token = governed.register_agent("usage-agent", ["goal:execute"])
            summary = run_async(
                run_hermetic_think_job(
                    governed,
                    "tokens",
                    subtasks,
                    complete,
                    token_value=token,
                    agent_id="usage-agent",
                    manager=mgr,
                )
            )
            proof = verify_dag_proof_file(Path(summary["proof_artifact"]))
            self.assertEqual(proof["tasks"][0]["tokens"], 17)

    def test_hermetic_outputs_secrets_clean(self) -> None:
        subtasks = [subtask_spec("distractor", "wrongkey")]
        provider = HermeticModelProvider(subtasks, {0: "wrongkey_then_valid"})
        complete = provider_complete_async(provider)
        with temp_experiment_stack() as (mgr, db_path, art_dir):
            ledger = str(Path(db_path).parent / "ledger.db")
            governed = make_governed(ledger_path=ledger)
            token = governed.register_agent("clean-agent", ["goal:execute"])
            summary = run_async(
                run_hermetic_think_job(
                    governed,
                    "secrets scan",
                    subtasks,
                    complete,
                    token_value=token,
                    agent_id="clean-agent",
                    manager=mgr,
                )
            )
            blob = collect_hermetic_artifact_blob(art_dir, summary, ledger)
            assert_hermetic_blob_has_no_secrets(blob)
            self.assertTrue(secrets_clean(summary))


class TestF023PrepIntegration(unittest.TestCase):
    def test_prep_module_still_importable_alongside_lifecycle(self) -> None:
        from tests.e2e import test_f023_prep  # noqa: F401

        self.assertTrue(hasattr(test_f023_prep, "TestExperimentPersistenceOnDisk"))


if __name__ == "__main__":
    unittest.main()
