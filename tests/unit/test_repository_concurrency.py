"""Job files under concurrent use by separate Repository instances.

open_lifecycle_repo() returns a new Repository on every call, so each caller has its own threading lock. The
single-claim guarantee for a queued job (resume_queued_job) therefore rests on the job file itself: a reader
must never see a half-written file, and a compare-and-set must have exactly one winner.
"""

from __future__ import annotations

import tempfile
import threading
import unittest

from thinkbox.repository import Repository


def _open(path: str) -> Repository:
    return Repository(path, enforce_git=False)


class TestJobFileIsNeverHalfWritten(unittest.TestCase):
    def test_a_reader_never_sees_a_missing_job_while_it_is_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            writer = _open(d)
            writer.create_job(job_id="job_rw", intent="x")
            stop = threading.Event()
            misses: list[int] = []

            def read() -> None:
                reader = _open(d)
                while not stop.is_set():
                    if reader.job_status("job_rw") is None:
                        misses.append(1)

            thread = threading.Thread(target=read)
            thread.start()
            try:
                for i in range(300):
                    writer.update_job("job_rw", metadata={"n": i, "pad": "x" * 20000})
            finally:
                stop.set()
                thread.join()
            self.assertEqual(misses, [], f"{len(misses)} reads found no job while it was being rewritten")


class TestCompareAndSet(unittest.TestCase):
    def test_exactly_one_instance_wins_a_claim(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _open(d)
            for round_no in range(40):
                job_id = f"job_cas_{round_no}"
                _open(d).create_job(job_id=job_id, intent="x", metadata={"governed_lifecycle": {"phase": "queued"}})
                barrier = threading.Barrier(6)
                winners: list[int] = []

                def claim(owner: int) -> None:
                    repo = _open(d)
                    barrier.wait()
                    won = repo.update_job(
                        job_id,
                        status="running",
                        metadata={"governed_lifecycle": {"phase": "running", "owner": owner}},
                        require_lifecycle_phase="queued",
                    )
                    if won is not None:
                        winners.append(owner)

                threads = [threading.Thread(target=claim, args=(i,)) for i in range(6)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
                self.assertEqual(len(winners), 1, f"round {round_no}: claimed by {winners}")
                final = _open(d).job_status(job_id)
                assert final is not None
                self.assertEqual(final["metadata"]["governed_lifecycle"]["owner"], winners[0])

    def test_ensure_job_creates_once_and_keeps_later_changes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            first = _open(d).ensure_job("job_once", intent="first")
            self.assertEqual(first["intent"], "first")
            _open(d).update_job("job_once", metadata={"k": 1})
            again = _open(d).ensure_job("job_once", intent="second")
            self.assertEqual(again["intent"], "first")
            self.assertEqual(again["metadata"]["k"], 1)

    def test_concurrent_ensure_job_calls_agree_on_one_job(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _open(d)
            barrier = threading.Barrier(6)
            seen: list[tuple[str, str]] = []

            def ensure(owner: int) -> None:
                repo = _open(d)
                barrier.wait()
                snap = repo.ensure_job("job_conc", intent=f"caller-{owner}")
                seen.append((snap["intent"], snap["created_at"]))

            threads = [threading.Thread(target=ensure, args=(i,)) for i in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(len(set(seen)), 1, f"callers saw different jobs: {sorted(set(seen))}")


if __name__ == "__main__":
    unittest.main()
