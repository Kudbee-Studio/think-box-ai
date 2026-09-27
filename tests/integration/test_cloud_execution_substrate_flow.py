"""Integration: job → admission → provider → worker → receipt (PR #197)."""

from __future__ import annotations

import unittest

from thinkbox.cloud_execution.engine import CloudExecutionEngine
from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.providers.hermetic import HermeticCloudExecutionProvider, PROVIDER_NAME
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding


class TestCloudExecutionIntegration(unittest.TestCase):
    def test_end_to_end_hermetic(self) -> None:
        limits = ResourceLimits(
            cpu_cores=1.0,
            memory_mb=256,
            wall_clock_timeout_s=60.0,
            max_concurrency=1,
        )
        workspace = WorkspaceBinding(
            workspace_id="wt_integration_1",
            worktree_path="/tmp/thinkbox/wt_integration_1",
            git_branch="feat/test",
        )
        engine = CloudExecutionEngine(HermeticCloudExecutionProvider())
        job = engine.submit_intent("integration smoke", limits, workspace)
        receipt = engine.execute(job, limits, workspace)
        snap = receipt.snapshot()
        self.assertEqual(snap["provider"], PROVIDER_NAME)
        self.assertEqual(snap["lifecycle_state"], ExecutionJobState.SUCCEEDED.value)
        self.assertFalse(snap["live_api_called"])
        self.assertIn("artifact://hermetic/", snap["artifact_refs"][0])


if __name__ == "__main__":
    unittest.main()
