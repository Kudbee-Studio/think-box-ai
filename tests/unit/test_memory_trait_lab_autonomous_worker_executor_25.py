"""Hermetic tests for Trait Lab autonomous worker executor L01–L25."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from thinkbox.autonomous_worker_executor import (
    TRAIT_LAB_AUTONOMOUS_WORKER_EXECUTOR_OPS,
    assert_trait_lab_autonomous_worker_executor_ok,
    bundle_trait_lab_autonomous_worker_executor_for_ci,
    manifest_trait_lab_autonomous_worker_executor_config,
    open_trait_lab_autonomous_worker_executor,
    plan_trait_lab_autonomous_worker_executor,
    refuse_trait_lab_autonomous_worker_executor_live,
    sign_trait_lab_autonomous_worker_executor,
    verify_trait_lab_autonomous_worker_executor,
)
from thinkbox.memory_layers import MemoryLayerError


class TestMemoryTraitLabAutonomousWorkerExecutor25(unittest.TestCase):
    def test_l00_ops_catalog(self) -> None:
        self.assertEqual(len(TRAIT_LAB_AUTONOMOUS_WORKER_EXECUTOR_OPS), 25)

    def test_l01_l07_plan(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            refuse_trait_lab_autonomous_worker_executor_live({"live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")
        signed = sign_trait_lab_autonomous_worker_executor(
            plan_trait_lab_autonomous_worker_executor(gate_mode="gate_regression")
        )
        self.assertTrue(verify_trait_lab_autonomous_worker_executor(signed)["matched"])
        manifest = manifest_trait_lab_autonomous_worker_executor_config(signed)
        self.assertIn("gate_mode", manifest)
        self.assertIn("worker_sha256", manifest)

    def test_l08_l25_gate_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            from thinkbox.cloud_execution.durable_engine import DurableCloudExecutionEngine
            from thinkbox.cloud_execution.providers.hermetic import HermeticCloudExecutionProvider
            from thinkbox.cloud_execution.workspace import WorkspaceRegistry

            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                Path(td) / "jobs.db",
                workspace_registry=WorkspaceRegistry(),
                run_recovery=False,
            )
            # Enqueue a simple job
            from thinkbox.cloud_execution.resources import ResourceLimits
            from thinkbox.cloud_execution.workspace import WorkspaceBinding
            engine.enqueue_intent(
                "test job",
                ResourceLimits(1.0, 256, 30.0, 1),
                WorkspaceBinding("test_ws", "/tmp/test_ws"),
                job_id="test_job_1",
            )

            opened = open_trait_lab_autonomous_worker_executor(
                agent_id="unit",
                task_id="l25-gate",
                environ={},
                engine=engine,
                gate_mode="gate",
                max_claims=1,
                budget=1,
            )
            self.assertTrue(opened["worker_open"])
            self.assertEqual(len(opened["cycle_results"]), 1)
            assert_trait_lab_autonomous_worker_executor_ok(opened)
            bundle = bundle_trait_lab_autonomous_worker_executor_for_ci(opened)
            self.assertTrue(bundle["report"]["ok"])

    def test_l08_l25_gate_regression(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            from thinkbox.cloud_execution.durable_engine import DurableCloudExecutionEngine
            from thinkbox.cloud_execution.providers.hermetic import HermeticCloudExecutionProvider
            from thinkbox.cloud_execution.workspace import WorkspaceRegistry

            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                Path(td) / "jobs.db",
                workspace_registry=WorkspaceRegistry(),
                run_recovery=False,
            )
            from thinkbox.cloud_execution.resources import ResourceLimits
            from thinkbox.cloud_execution.workspace import WorkspaceBinding
            engine.enqueue_intent(
                "test job",
                ResourceLimits(1.0, 256, 30.0, 1),
                WorkspaceBinding("test_ws", "/tmp/test_ws"),
                job_id="test_job_2",
            )

            opened = open_trait_lab_autonomous_worker_executor(
                agent_id="unit",
                task_id="l25-full",
                environ={},
                engine=engine,
                gate_mode="gate_regression",
                max_claims=1,
                budget=1,
            )
            self.assertTrue(opened["ok"])
            self.assertEqual(len(opened["cycle_results"]), 1)
            assert_trait_lab_autonomous_worker_executor_ok(opened)


if __name__ == "__main__":
    unittest.main()