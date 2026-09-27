"""Integration: intent → queue → worker → heartbeat → hermetic → receipt."""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path

from thinkbox.cloud_execution.durable_engine import DurableCloudExecutionEngine
from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.providers.hermetic import HermeticCloudExecutionProvider
from thinkbox.cloud_execution.queue_model import QueueDisposition
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.worker_config import WorkerConfig
from thinkbox.cloud_execution.worker_inspection import inspect_worker
from thinkbox.cloud_execution.worker_orchestrator import CloudExecutionWorker
from thinkbox.cloud_execution.workspace import WorkspaceBinding, WorkspaceRegistry


class TestWorkerOrchestratorIntegration(unittest.TestCase):
    def test_full_worker_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "worker_flow.db"
            limits = ResourceLimits(1.0, 256, 30.0, 1)
            workspace = WorkspaceBinding(
                workspace_id="wt_worker_flow",
                worktree_path="/tmp/thinkbox/wt_worker_flow",
            )
            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                db,
                workspace_registry=WorkspaceRegistry(),
                run_recovery=False,
            )
            engine.enqueue_intent(
                "worker integration",
                limits,
                workspace,
                job_id="cex_worker_flow_1",
            )
            worker = CloudExecutionWorker(
                engine,
                WorkerConfig(worker_id="flow-worker-1"),
                persist_runtime=False,
            )
            worker.start()
            worker.beat()
            worker.renew_active_claims()
            self.assertEqual(worker.run_until_idle(), 1)
            view = inspect_worker(worker)
            self.assertEqual(view["successful_jobs"], 1)
            self.assertFalse(view["live_api_called"])
            job = engine.durable_store.get("cex_worker_flow_1")
            self.assertEqual(job.state, ExecutionJobState.SUCCEEDED)
            row = engine.durable_store.get_record("cex_worker_flow_1")
            self.assertEqual(row.queue_disposition, QueueDisposition.COMPLETED)

    def test_two_workers_one_job(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "dual.db"
            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                db,
                run_recovery=False,
            )
            engine.enqueue_intent(
                "once",
                ResourceLimits(1.0, 128, 10.0, 1),
                WorkspaceBinding("w_dual", "/tmp/w_dual"),
                job_id="dual_job",
            )
            winners: list[str] = []

            def loop(wid: str) -> None:
                eng = DurableCloudExecutionEngine(
                    HermeticCloudExecutionProvider(),
                    db,
                    run_recovery=False,
                )
                w = CloudExecutionWorker(
                    eng,
                    WorkerConfig(worker_id=wid),
                    persist_runtime=False,
                )
                w.start()
                if w.poll_once():
                    winners.append(wid)

            threads = [threading.Thread(target=loop, args=(f"worker-{i}",)) for i in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(winners), 1)
            self.assertEqual(engine.durable_store.get("dual_job").state, ExecutionJobState.SUCCEEDED)


if __name__ == "__main__":
    unittest.main()
