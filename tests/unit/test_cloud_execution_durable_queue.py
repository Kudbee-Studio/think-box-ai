"""Durable queue tests (PR #198)."""

from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from thinkbox import kilo_pr198_cloud_execution_durable_queue as pr198
from thinkbox.cloud_execution.admission_token import DisabledAdmissionTokenHook
from thinkbox.cloud_execution.durable_engine import DurableCloudExecutionEngine
from thinkbox.cloud_execution.errors import AdmissionDeniedError, CloudExecutionError
from thinkbox.cloud_execution.inspection import inspect_queue
from thinkbox.cloud_execution.job import ExecutionJobState
from thinkbox.cloud_execution.providers.hermetic import HermeticCloudExecutionProvider
from thinkbox.cloud_execution.queue import ExecutionJobQueue
from thinkbox.cloud_execution.queue_model import QueueDisposition
from thinkbox.cloud_execution.recovery import recover_after_restart
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.sqlite_store import DurableExecutionJobStore
from thinkbox.cloud_execution.workspace import WorkspaceBinding, WorkspaceRegistry


def _limits() -> ResourceLimits:
    return ResourceLimits(1.0, 512, 60.0, 1)


def _ws(wid: str) -> WorkspaceBinding:
    return WorkspaceBinding(workspace_id=wid, worktree_path=f"/tmp/wt/{wid}")


class TestPr198Gate(unittest.TestCase):
    def test_manifest(self) -> None:
        ok, v = pr198.validate_features_manifest()
        self.assertTrue(ok, v)


class TestDurablePersistence(unittest.TestCase):
    def test_survives_store_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "jobs.db"
            store = DurableExecutionJobStore(path)
            q = ExecutionJobQueue(store)
            rec = q.enqueue("persist me", _limits(), _ws("wt_p1"), "hermetic_local", job_id="cex_job_fixed1")
            store.close()
            store2 = DurableExecutionJobStore(path)
            got = store2.get_record("cex_job_fixed1")
            self.assertIsNotNone(got)
            self.assertEqual(got.job.intent, "persist me")
            self.assertEqual(got.queue_disposition, QueueDisposition.QUEUED)


class TestQueueOperations(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self._path = Path(self._td.name) / "q.db"
        self._store = DurableExecutionJobStore(self._path)
        self._queue = ExecutionJobQueue(self._store, claim_lease_s=60.0)

    def tearDown(self) -> None:
        self._store.close()
        self._td.cleanup()

    def test_enqueue_and_claim(self) -> None:
        self._queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
        claimed = self._queue.claim("worker-1")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.queue_disposition, QueueDisposition.CLAIMED)

    def test_duplicate_job_id(self) -> None:
        self._queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local", job_id="dup_id")
        with self.assertRaises(CloudExecutionError):
            self._queue.enqueue("b", _limits(), _ws("w2"), "hermetic_local", job_id="dup_id")

    def test_duplicate_claim_prevention(self) -> None:
        self._queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
        c1 = self._queue.claim("worker-1")
        self.assertIsNotNone(c1)
        c2 = self._queue.claim("worker-2")
        self.assertIsNone(c2)

    def test_complete_and_fail(self) -> None:
        rec = self._queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
        claimed = self._queue.claim("w")
        self.assertIsNotNone(claimed)
        token = claimed.claim_token
        self._queue.complete(rec.job.job_id, token or "")
        done = self._store.list_by_disposition(QueueDisposition.COMPLETED)
        self.assertEqual(len(done), 1)

    def test_cancel(self) -> None:
        rec = self._queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
        self._queue.cancel(rec.job.job_id)
        self.assertEqual(len(self._store.list_by_disposition(QueueDisposition.CANCELLED)), 1)

    def test_retry_limits(self) -> None:
        from thinkbox.cloud_execution.retry_policy import RetryPolicy

        q = ExecutionJobQueue(self._store, RetryPolicy(max_retries=1))
        rec = q.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
        job = rec.job
        job.state = ExecutionJobState.FAILED
        job.metadata["last_exit_code"] = 1
        self._store.put(job)
        self._store.update_queue_fields(rec.job.job_id, disposition=QueueDisposition.FAILED)
        q.retry(rec.job.job_id)
        job.state = ExecutionJobState.FAILED
        self._store.put(job)
        self._store.update_queue_fields(rec.job.job_id, disposition=QueueDisposition.FAILED)
        with self.assertRaises(CloudExecutionError):
            q.retry(rec.job.job_id)

    def test_non_retryable_timeout(self) -> None:
        rec = self._queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
        job = rec.job
        job.state = ExecutionJobState.TIMED_OUT
        self._store.put(job)
        with self.assertRaises(CloudExecutionError):
            self._queue.retry(rec.job.job_id)

    def test_stale_claim_released(self) -> None:
        rec = self._queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
        claimed = self._queue.claim("w")
        self.assertIsNotNone(claimed)
        past = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        self._store.update_queue_fields(
            rec.job.job_id,
            claim_lease_until=past,
        )
        released = self._queue.release_stale_claims()
        self.assertIn(rec.job.job_id, released)
        self.assertEqual(len(self._store.list_by_disposition(QueueDisposition.QUEUED)), 1)

    def test_restart_recovery_running_blocked(self) -> None:
        rec = self._queue.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
        job = rec.job
        job.state = ExecutionJobState.RUNNING
        self._store.put(job)
        summary = recover_after_restart(self._store)
        self.assertIn(rec.job.job_id, summary["blocked_incomplete_runs"])
        got = self._store.get(rec.job.job_id)
        self.assertEqual(got.state, ExecutionJobState.BLOCKED)

    def test_concurrent_claim_attempts(self) -> None:
        for i in range(3):
            self._queue.enqueue(f"j{i}", _limits(), _ws(f"w{i}"), "hermetic_local")
        results: list[str | None] = []

        def worker(wid: str) -> None:
            c = self._queue.claim(wid)
            results.append(c.job.job_id if c else None)

        threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        claimed_ids = [r for r in results if r]
        self.assertEqual(len(set(claimed_ids)), len(claimed_ids))


class TestDurableEngine(unittest.TestCase):
    def test_hermetic_through_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                Path(td) / "e.db",
                run_recovery=False,
            )
            rec = engine.enqueue_intent("run", _limits(), _ws("wt_e2e"))
            claimed = engine.queue.claim("worker-a")
            self.assertIsNotNone(claimed)
            receipt = engine.run_claimed(claimed, claimed.claim_token or "")
            self.assertFalse(receipt.live_api_called)
            self.assertEqual(receipt.lifecycle_state, ExecutionJobState.SUCCEEDED)

    def test_admission_denial(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            provider = HermeticCloudExecutionProvider()
            provider.set_available(False)
            engine = DurableCloudExecutionEngine(provider, Path(td) / "e.db", run_recovery=False)
            rec = engine.enqueue_intent("x", _limits(), _ws("wt_denied"))
            claimed = engine.queue.claim("w")
            self.assertIsNotNone(claimed)
            with self.assertRaises(AdmissionDeniedError):
                engine.run_claimed(claimed, claimed.claim_token or "")

    def test_workspace_binding_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "e.db"
            ws = _ws("wt_bind")
            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                path,
                workspace_registry=WorkspaceRegistry(),
                run_recovery=False,
            )
            engine.enqueue_intent("x", _limits(), ws, job_id="job_ws_1")
            store = DurableExecutionJobStore(path)
            got = store.get_record("job_ws_1")
            self.assertEqual(got.workspace.workspace_id, "wt_bind")

    def test_inspection_api(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "e.db"
            store = DurableExecutionJobStore(path)
            q = ExecutionJobQueue(store)
            q.enqueue("a", _limits(), _ws("w1"), "hermetic_local")
            view = inspect_queue(store, q)
            self.assertEqual(len(view["queued"]), 1)
            self.assertFalse(view["live_api_called"])

    def test_admission_token_hook_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hook = DisabledAdmissionTokenHook(enabled=True)
            engine = DurableCloudExecutionEngine(
                HermeticCloudExecutionProvider(),
                Path(td) / "e.db",
                admission_token_hook=hook,
                run_recovery=False,
            )
            with self.assertRaises(AdmissionDeniedError):
                engine.enqueue_intent("x", _limits(), _ws("w"), admission_token=None)


if __name__ == "__main__":
    unittest.main()
