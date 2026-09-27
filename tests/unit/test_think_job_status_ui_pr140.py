"""PR #140 parity between deep-link targets and #139 watch helpers."""

from __future__ import annotations

import unittest

from thinkbox.control_plane_deep_link import merge_deep_link_sources
from thinkbox.think_job_status_ui import poll_path_for_target, resolve_watch_target


class TestThinkJobStatusUiPr140(unittest.TestCase):
    def test_deep_link_resolves_same_poll_path(self) -> None:
        rid = "tb_sess_rcpt_pr140sample"
        link = merge_deep_link_sources(query_string=f"receipt_id={rid}")
        target = resolve_watch_target(receipt_id=link.receipt_id)
        self.assertEqual(poll_path_for_target(target), f"/api/v1/run/job/by-receipt/{rid}/status")


if __name__ == "__main__":
    unittest.main()
