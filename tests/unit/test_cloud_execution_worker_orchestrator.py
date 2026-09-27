"""Worker orchestrator tests (PR #199)."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from thinkbox import kilo_pr199_cloud_execution_worker_orchestrator as pr199
from thinkbox.cloud_execution.admission import ExecutionAdmissionGate
from thinkbox.cloud_execution.durable_engine import DurableCloudExecutionEngine
from thinkbox.cloud_execution.errors import AdmissionDeniedError, CloudExecutionError
from thinkbox.cloud_execution.heartbeat import HeartbeatStatus
from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.providers.hermetic import HermeticCloudExecutionProvider
from thinkbox.cloud_execution.queue import ExecutionJobQueue
from thinkbox.cloud_execution.queue_model import QueueDisposition
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.worker_config import WorkerConfig
from thinkbox.cloud_execution.worker_inspection import inspect_worker
from thinkbox.cloud_execution.worker_lifecycle import WorkerState, worker_transition
from thinkbox.cloud_execution.retry_policy import RetryPolicy
from thinkbox.cloud_execution.worker_orchestrator import CloudExecutionWorker, _ActiveClaim
from thinkbox.cloud_execution.worker_runtime_store import WorkerRuntimeStore
from thinkbox.cloud_execution.workspace import WorkspaceBinding, WorkspaceRegistry


def _limits() -> ResourceLimits:
    return ResourceLimits(1.0, 512, 60.0, 1)


def _ws(wid: str) -> WorkspaceBinding:
    return WorkspaceBinding(workspace_id=wid, worktree_path=f"/tmp/wt/{wid}")


def _engine(td: str, *, recovery: bool = False) -> DurableCloudExecutionEngine:
    return DurableCloudExecutionEngine(
        HermeticCloudExecutionProvider(),
        Path(td) / "jobs.db",
        workspace_registry=WorkspaceRegistry(),
        run_recovery=recovery,
    )


def _worker(engine: DurableCloudExecutionEngine, worker_id: str = "w-1") -> CloudExecutionWorker:
    cfg = WorkerConfig(worker_id=worker_id, max_active_jobs=1, heartbeat_interval_s=0.5, heartbeat_timeout_s=2.0)
    w = CloudExecutionWorker(engine, cfg)
    w.start()
    return w


class TestPr199Gate(unittest.TestCase):
    def test_manifest(self) -> None:
        ok, v = pr199.validate_features_manifest()
        self.assertTrue(ok, v)


class TestWorkerLifecycle(unittest.TestCase):
    def test_happy_path_transitions(self) -> None:
        self.assertEqual(worker_transition(WorkerState.STARTING, WorkerState.IDLE), WorkerState.IDLE)
        self.assertEqual(worker_transition(WorkerState.IDLE, WorkerState.CLAIMING), WorkerState.CLAIMING)

    def test_invalid_transition_fail_closed(self) -> None:
        with self.assertRaises(CloudExecutionError):
            worker_transition(WorkerState.STOPPED, WorkerState.IDLE)


class TestWorkerStartupShutdown(unittest.TestCase):
    def test_startup_and_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = _engine(td)
            worker = _worker(engine)
            self.assertEqual(worker.state, WorkerState.IDLE)
            worker.request_shutdown()
            self.assertEqual(worker.state, WorkerState.DRAINING)
            worker.run_until_idle()
            self.assertEqual(worker.state, WorkerState.STOPPED)
            view = inspect_worker(worker)
            self.assertEqual(view["worker_id"], "w-1")
            self.assertIsNotNone(view["stopped_reason"])

    def test_runtime_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "jobs.db"
            engine = _engine(td)
            store = WorkerRuntimeStore(db)
            worker = CloudExecutionWorker(
                engine,
                WorkerConfig(worker_id="persist-w"),
                runtime_store=store,
            )
            worker.start()
            loaded = store.load_snapshot("persist-w")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["state"], WorkerState.IDLE.value)


class TestWorkerQueueExecution(unittest.TestCase):
    def test_successful_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = _engine(td)
            worker = _worker(engine)
            engine.enqueue_intent("ok", _limits(), _ws("w1"), job_id="job_ok")
            n = worker.run_until_idle()
            self.assertEqual(n, 1)
            job = engine.durable_store.get("job_ok")
            self.assertEqual(job.state, ExecutionJobState.SUCCEEDED)
            self.assertIsNotNone(engine.durable_store.get_record("job_ok"))

    def test_multiple_queued_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = _engine(td)
            worker = _worker(engine)
            for i in range(3):
                engine.enqueue_intent(f"j{i}", _limits(), _ws(f"w{i}"), job_id=f"job_{i}")
            self.assertEqual(worker.run_until_idle(), 3)
            view = inspect_worker(worker)
            self.assertEqual(view["successful_jobs"], 3)

    def test_failed_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = _engine(td)
            worker = _worker(engine)
            engine.enqueue_intent(
                "fail",
                _limits(),
                _ws("wf"),
                job_id="job_fail",
                metadata={"hermetic_scenario": "fail"},
            )
            worker.run_until_idle()
            job = engine.durable_store.get("job_fail")
            self.assertEqual(job.state, ExecutionJobState.FAILED)

    def test_retryable_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                Path(td) / "jobs.db",
                run_recovery=False,
                retry_policy=RetryPolicy(max_retries=2),
            )
            worker = _worker(engine)
            engine.enqueue_intent(
                "retry",
                _limits(),
                _ws("wr"),
                job_id="job_retry",
                metadata={"hermetic_scenario": "fail"},
            )
            worker.run_until_idle(max_iterations=10)
            final = engine.durable_store.get_record("job_retry")
            self.assertIsNotNone(final)
            self.assertIn(
                final.queue_disposition,
                (QueueDisposition.COMPLETED, QueueDisposition.FAILED, QueueDisposition.QUEUED),
            )

    def test_non_retryable_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = _engine(td)
            worker = _worker(engine)
            engine.enqueue_intent(
                "to",
                _limits(),
                _ws("wt"),
                job_id="job_to",
                metadata={"hermetic_scenario": "timeout"},
            )
            worker.run_until_idle()
            job = engine.durable_store.get("job_to")
            self.assertEqual(job.state, ExecutionJobState.TIMED_OUT)
            with self.assertRaises(CloudExecutionError):
                engine.queue.retry("job_to")

    def test_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = _engine(td)
            worker = _worker(engine)
            engine.enqueue_intent(
                "c",
                _limits(),
                _ws("wc"),
                job_id="job_cancel",
                metadata={"hermetic_scenario": "cancel"},
            )
            worker.run_until_idle()
            job = engine.durable_store.get("job_cancel")
            self.assertEqual(job.state, ExecutionJobState.CANCELLED)

    def test_admission_denial(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            provider = HermeticCloudExecutionProvider()
            provider.set_available(False)
            engine = DurableCloudExecutionEngine(provider, Path(td) / "jobs.db", run_recovery=False)
            worker = _worker(engine)
            engine.enqueue_intent("x", _limits(), _ws("wd"))
            worker.run_until_idle()
            view = inspect_worker(worker)
            self.assertGreaterEqual(view["failed_jobs"], 1)


class TestClaimAndHeartbeat(unittest.TestCase):
    def test_heartbeat_renewal_extends_lease(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = __import__(
                "thinkbox.cloud_execution.sqlite_store",
                fromlist=["DurableExecutionJobStore"],
            ).DurableExecutionJobStore(Path(td) / "q.db")
            queue = ExecutionJobQueue(store, claim_lease_s=2.0)
            queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
            claimed = queue.claim("worker-hb")
            self.assertIsNotNone(claimed)
            token = claimed.claim_token or ""
            self.assertTrue(queue.renew_claim(claimed.job.job_id, "worker-hb", token))

    def test_stale_worker_heartbeat_status(self) -> None:
        hb = __import__(
            "thinkbox.cloud_execution.heartbeat",
            fromlist=["WorkerHeartbeat"],
        ).WorkerHeartbeat("w", "1970-01-01T00:00:00+00:00", 0.5, 1.0)
        self.assertEqual(hb.status().value, HeartbeatStatus.TIMED_OUT.value)

    def test_healthy_worker_continues(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = _engine(td)
            worker = _worker(engine)
            worker.beat()
            self.assertEqual(worker.heartbeat.status(), HeartbeatStatus.ACTIVE)
            engine.enqueue_intent("x", _limits(), _ws("w1"))
            self.assertTrue(worker.poll_once())

    def test_expired_claim_cannot_execute(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "e.db"
            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                path,
                run_recovery=False,
            )
            engine.queue._claim_lease_s = 0.01
            rec = engine.enqueue_intent("x", _limits(), _ws("w1"), job_id="exp_job")
            claimed = engine.queue.claim("w-exp")
            self.assertIsNotNone(claimed)
            past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
            engine.durable_store.update_queue_fields(
                rec.job.job_id,
                claim_lease_until=past,
            )
            with self.assertRaises(CloudExecutionError):
                engine.run_claimed(claimed, claimed.claim_token or "", worker_id="w-exp")

    def test_shutdown_requeue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = _engine(td)
            worker = _worker(engine)
            rec = engine.enqueue_intent("x", _limits(), _ws("w1"))
            claimed = engine.queue.claim(worker.config.worker_id)
            self.assertIsNotNone(claimed)
            worker._active[rec.job.job_id] = _ActiveClaim(claimed, claimed.claim_token or "")
            worker.request_shutdown()
            worker.settle_shutdown()
            self.assertEqual(worker.state, WorkerState.STOPPED)
            row = engine.durable_store.get_record(rec.job.job_id)
            self.assertEqual(row.queue_disposition, QueueDisposition.QUEUED)


class TestConcurrencyAndRecovery(unittest.TestCase):
    def test_concurrent_workers_no_duplicate_claim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "shared.db"
            for i in range(5):
                eng = DurableCloudExecutionEngine(
                    HermeticCloudExecutionProvider(),
                    db,
                    run_recovery=False,
                )
                if i == 0:
                    eng.enqueue_intent("only", _limits(), _ws("w0"), job_id="solo")
            results: list[str | None] = []

            def run_worker(wid: str) -> None:
                eng = DurableCloudExecutionEngine(
                    HermeticCloudExecutionProvider(),
                    db,
                    run_recovery=False,
                )
                w = CloudExecutionWorker(eng, WorkerConfig(worker_id=wid), persist_runtime=False)
                w.start()
                if w.poll_once():
                    results.append(wid)

            threads = [threading.Thread(target=run_worker, args=(f"c-{i}",)) for i in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len([r for r in results if r]), 1)

    def test_restart_recovery_with_worker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "r.db"
            eng1 = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                path,
                run_recovery=True,
            )
            eng1.enqueue_intent("q", _limits(), _ws("wr"), job_id="rec_job")
            eng2 = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                path,
                run_recovery=True,
            )
            worker = _worker(eng2)
            self.assertIn("recovery_summary", inspect_worker(worker))
            worker.run_until_idle()
            self.assertEqual(eng2.durable_store.get("rec_job").state, ExecutionJobState.SUCCEEDED)

    def test_receipt_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rc.db"
            engine = _engine(td)
            worker = _worker(engine)
            engine.enqueue_intent("r", _limits(), _ws("w1"), job_id="rcpt")
            worker.run_until_idle()
            row = engine.durable_store.get_record("rcpt")
            self.assertIsNotNone(row)
            with engine.durable_store._lock:
                raw = engine.durable_store._conn.execute(
                    "SELECT last_receipt_json FROM cloud_execution_jobs WHERE job_id = ?",
                    ("rcpt",),
                ).fetchone()
            self.assertIsNotNone(raw[0])
            doc = json.loads(raw[0])
            self.assertFalse(doc.get("live_api_called", True))

    def test_inspection_api(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            worker = _worker(_engine(td))
            view = inspect_worker(worker)
            self.assertEqual(view["capacity"], 1)
            self.assertEqual(view["claim_count"], 0)
            self.assertFalse(view["live_api_called"])


if __name__ == "__main__":
    unittest.main()
