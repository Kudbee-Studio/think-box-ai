"""PR #134 review: list endpoint payload shape."""

from __future__ import annotations

import unittest

from backend.api.v1.run_job_status import list_recent_think_job_statuses
from thinkbox.dashboard_state import ThinkJobEntry, get_dashboard_state


class TestListJobStatusReview(unittest.TestCase):
    def test_list_entries_include_poll_block(self) -> None:
        dash = get_dashboard_state()
        dash.think_jobs.clear()
        dash.upsert_think_job(ThinkJobEntry(job_id="j", goal="g", status="running"))
        rows = list_recent_think_job_statuses(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertIn("poll", rows[0])
        self.assertIn("receipt_card", rows[0])


if __name__ == "__main__":
    unittest.main()
