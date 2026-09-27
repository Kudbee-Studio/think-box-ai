"""Unit tests for cloud execution substrate (PR #197)."""

from __future__ import annotations

import unittest

from thinkbox import kilo_pr197_cloud_execution_substrate as pr197
from thinkbox.cloud_execution.admission import ExecutionAdmissionGate
from thinkbox.cloud_execution.engine import CloudExecutionEngine
from thinkbox.cloud_execution.errors import AdmissionDeniedError, InvalidTransitionError
from thinkbox.cloud_execution.heartbeat import HeartbeatStatus, WorkerHeartbeat
from thinkbox.cloud_execution.job import ExecutionJob, ExecutionJobState
from thinkbox.cloud_execution.lifecycle import assert_transition, transition
from thinkbox.cloud_execution.providers.hermetic import HermeticCloudExecutionProvider, PROVIDER_NAME
from thinkbox.cloud_execution.receipt import ExecutionAttemptReceipt
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding, WorkspaceRegistry


def _limits(**kwargs: object) -> ResourceLimits:
    return ResourceLimits(
        cpu_cores=float(kwargs.get("cpu_cores", 1.0)),
        memory_mb=int(kwargs.get("memory_mb", 512)),
        wall_clock_timeout_s=float(kwargs.get("wall_clock_timeout_s", 30.0)),
        max_concurrency=int(kwargs.get("max_concurrency", 1)),
    )


def _ws(wid: str = "wt_test_1") -> WorkspaceBinding:
    return WorkspaceBinding(workspace_id=wid, worktree_path=f"/tmp/worktrees/{wid}")


class TestPr197Manifest(unittest.TestCase):
    def test_manifest_valid(self) -> None:
        ok, v = pr197.validate_features_manifest()
        self.assertTrue(ok, v)


class TestLifecycle(unittest.TestCase):
    def test_happy_path_transitions(self) -> None:
        s = ExecutionJobState.QUEUED
        for target in (
            ExecutionJobState.ADMITTED,
            ExecutionJobState.STARTING,
            ExecutionJobState.RUNNING,
            ExecutionJobState.SUCCEEDED,
        ):
            s = transition(s, target)
        self.assertEqual(s, ExecutionJobState.SUCCEEDED)

    def test_invalid_transition_fails_closed(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            assert_transition(ExecutionJobState.QUEUED, ExecutionJobState.RUNNING)

    def test_terminal_blocked(self) -> None:
        with self.assertRaises(InvalidTransitionError):
            assert_transition(ExecutionJobState.BLOCKED, ExecutionJobState.QUEUED)


class TestResourceLimits(unittest.TestCase):
    def test_invalid_cpu_denied(self) -> None:
        with self.assertRaises(AdmissionDeniedError):
            _limits(cpu_cores=0).validate()


class TestAdmission(unittest.TestCase):
    def test_provider_unavailable(self) -> None:
        provider = HermeticCloudExecutionProvider()
        provider.set_available(False)
        gate = ExecutionAdmissionGate(WorkspaceRegistry())
        job = ExecutionJob(intent="x")
        with self.assertRaises(AdmissionDeniedError):
            gate.admit(job, _limits(), _ws(), provider)

    def test_workspace_conflict(self) -> None:
        reg = WorkspaceRegistry()
        gate = ExecutionAdmissionGate(reg)
        provider = HermeticCloudExecutionProvider()
        job1 = ExecutionJob(intent="a")
        job2 = ExecutionJob(intent="b")
        ws = _ws("same")
        gate.admit(job1, _limits(), ws, provider)
        with self.assertRaises(AdmissionDeniedError):
            gate.admit(job2, _limits(), ws, provider)

    def test_policy_denial(self) -> None:
        def deny(_j: ExecutionJob, _l: ResourceLimits, _w: WorkspaceBinding) -> None:
            raise AdmissionDeniedError("policy deny")

        gate = ExecutionAdmissionGate(WorkspaceRegistry(), policy=deny)
        with self.assertRaises(AdmissionDeniedError):
            gate.admit(ExecutionJob(intent="x"), _limits(), _ws(), HermeticCloudExecutionProvider())


class TestHermeticProvider(unittest.TestCase):
    def test_success(self) -> None:
        provider = HermeticCloudExecutionProvider()
        job = ExecutionJob(intent="hello")
        result = provider.run(job, _limits(), _ws())
        self.assertTrue(result.success)
        self.assertEqual(result.exit_code, 0)

    def test_failure_scenario(self) -> None:
        provider = HermeticCloudExecutionProvider()
        job = ExecutionJob(intent="x", metadata={"hermetic_scenario": "fail"})
        result = provider.run(job, _limits(), _ws())
        self.assertFalse(result.success)

    def test_timeout_scenario(self) -> None:
        job = ExecutionJob(intent="x", metadata={"hermetic_scenario": "timeout"})
        result = HermeticCloudExecutionProvider().run(job, _limits(), _ws())
        self.assertEqual(result.exit_code, 124)

    def test_cancel_scenario(self) -> None:
        job = ExecutionJob(intent="x", metadata={"hermetic_scenario": "cancel"})
        result = HermeticCloudExecutionProvider().run(job, _limits(), _ws())
        self.assertEqual(result.exit_code, 130)

    def test_stale_heartbeat(self) -> None:
        job = ExecutionJob(intent="x", metadata={"hermetic_scenario": "stale_heartbeat"})
        result = HermeticCloudExecutionProvider().run(job, _limits(), _ws())
        self.assertIsNotNone(result.heartbeat)
        self.assertEqual(result.heartbeat.status(), HeartbeatStatus.TIMED_OUT)


class TestReceipt(unittest.TestCase):
    def test_cannot_claim_live(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionAttemptReceipt(
                job_id="j",
                execution_id="e",
                provider=PROVIDER_NAME,
                workspace_id="w",
                lifecycle_state=ExecutionJobState.SUCCEEDED,
                started_at="t",
                verification_class="LIVE_VERIFIED",
            )


class TestEngine(unittest.TestCase):
    def test_execute_success_receipt(self) -> None:
        engine = CloudExecutionEngine(HermeticCloudExecutionProvider())
        job = engine.submit_intent("run tests", _limits(), _ws("wt_a"))
        receipt = engine.execute(job, _limits(), _ws("wt_a"))
        self.assertFalse(receipt.live_api_called)
        self.assertEqual(receipt.verification_class, "TEST_VERIFIED")
        self.assertEqual(receipt.lifecycle_state, ExecutionJobState.SUCCEEDED)

    def test_concurrent_jobs_isolated_workspaces(self) -> None:
        engine = CloudExecutionEngine(HermeticCloudExecutionProvider())
        j1 = engine.submit_intent("one", _limits(), _ws("wt_1"))
        j2 = engine.submit_intent("two", _limits(), _ws("wt_2"))
        engine.execute(j1, _limits(), _ws("wt_1"))
        engine.execute(j2, _limits(), _ws("wt_2"))
        self.assertIsNone(engine.workspace_registry.bound_job("wt_1"))
        self.assertIsNone(engine.workspace_registry.bound_job("wt_2"))

    def test_duplicate_workspace_blocked(self) -> None:
        reg = WorkspaceRegistry()
        reg.bind(_ws("wt_shared"), "job_other")
        engine = CloudExecutionEngine(HermeticCloudExecutionProvider(), workspace_registry=reg)
        job = engine.submit_intent("two", _limits(), _ws("wt_shared"))
        with self.assertRaises(AdmissionDeniedError):
            engine.execute(job, _limits(), _ws("wt_shared"))


if __name__ == "__main__":
    unittest.main()
