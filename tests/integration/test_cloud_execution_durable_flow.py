"""Integration: intent → durable job → queue → claim → admission → hermetic → receipt."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from thinkbox.cloud_execution.durable_engine import DurableCloudExecutionEngine
from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.providers.hermetic import HermeticCloudExecutionProvider
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.sqlite_store import DurableExecutionJobStore
from thinkbox.cloud_execution.workspace import WorkspaceBinding


class TestDurableCloudExecutionFlow(unittest.TestCase):
    def test_full_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "flow.db"
            limits = ResourceLimits(1.0, 256, 30.0, 1)
            workspace = WorkspaceBinding(
                workspace_id="wt_flow_1",
                worktree_path="/tmp/thinkbox/wt_flow_1",
            )
            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                db,
                run_recovery=False,
            )
            enqueued = engine.enqueue_intent(
                "integration durable flow",
                limits,
                workspace,
                job_id="cex_job_flow_1",
            )
            self.assertEqual(enqueued.job.job_id, "cex_job_flow_1")
            claimed = engine.queue.claim("integration-worker")
            self.assertIsNotNone(claimed)
            receipt = engine.run_claimed(claimed, claimed.claim_token or "")
            self.assertEqual(receipt.lifecycle_state, ExecutionJobState.SUCCEEDED)
            store = DurableExecutionJobStore(db)
            row = store.get_record("cex_job_flow_1")
            self.assertIsNotNone(row)
            self.assertIsNotNone(row and store.get_record("cex_job_flow_1"))
            persisted = store.get("cex_job_flow_1")
            self.assertEqual(persisted.state, ExecutionJobState.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
