"""Hermetic tests for pipeline delta polling."""

from __future__ import annotations

import unittest

from thinkbox.pipeline_dashboard import PipelineDashboardAggregator, PipelineDeltaTracker
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore


class TestPipelineDeltaTracker(unittest.TestCase):
    def test_snapshot_detects_overview_change(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        aggregator = PipelineDashboardAggregator(store)
        tracker = PipelineDeltaTracker(aggregator)
        first = tracker.snapshot()
        self.assertTrue(first["changed"])
        second = tracker.snapshot()
        self.assertFalse(second["changed"])
        store.append_lifecycle(
            run_id="r",
            pr_number=701,
            branch="b",
            from_state="A",
            to_state="B",
            action="act",
            result="success",
        )
        third = tracker.snapshot()
        self.assertTrue(third["changed"])
        self.assertIsNotNone(third.get("overview"))


if __name__ == "__main__":
    unittest.main()
