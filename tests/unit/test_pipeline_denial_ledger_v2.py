from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import PipelineDashboardAggregator


class TestDenialLedgerV2(unittest.TestCase):
    def test_by_pr_breakdown(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        for pr in (10, 10, 20):
            store.append_lifecycle(
                run_id="r",
                pr_number=pr,
                branch="b",
                from_state="BLOCKED",
                to_state="BLOCKED",
                action="admission_denied",
                result="blocked",
            )
        agg = PipelineDashboardAggregator(store)
        ledger = agg.admission_denial_ledger()
        self.assertEqual(ledger["total_denials"], 3)
        self.assertEqual(ledger["by_pr"]["10"], 2)


if __name__ == "__main__":
    unittest.main()
