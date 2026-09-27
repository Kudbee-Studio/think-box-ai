"""Code-review follow-ups for PR #134 job status polling."""

from __future__ import annotations

import unittest

from backend.api.v1.run_job_status import poll_hints_for_status


class TestRunJobStatusReview(unittest.TestCase):
    def test_running_poll_interval_slower_than_terminal(self) -> None:
        running = poll_hints_for_status("running")["recommended_interval_ms"]
        done = poll_hints_for_status("completed")["recommended_interval_ms"]
        self.assertGreater(running, done)

    def test_failed_is_terminal(self) -> None:
        self.assertTrue(poll_hints_for_status("failed")["terminal"])


if __name__ == "__main__":
    unittest.main()
