"""Path helpers for Think Job status UI (PR #138)."""

from __future__ import annotations

import unittest

from thinkbox.think_job_status_ui import (
    format_job_poll_path,
    format_job_stream_path,
    format_jobs_digest_stream_path,
    format_receipt_stream_path,
)


class TestPathHelpers(unittest.TestCase):
    def test_job_paths(self) -> None:
        self.assertIn("eng1", format_job_poll_path("eng1"))
        self.assertIn("status/stream", format_job_stream_path("eng1"))

    def test_receipt_and_digest_paths(self) -> None:
        self.assertIn("receipt_x", format_receipt_stream_path("receipt_x"))
        self.assertIn("jobs/status/stream", format_jobs_digest_stream_path())


if __name__ == "__main__":
    unittest.main()
