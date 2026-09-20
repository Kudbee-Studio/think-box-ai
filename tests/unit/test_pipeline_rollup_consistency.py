from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_rollup_consistency import verify_pr_rollup_consistency


class TestRollupConsistency(unittest.TestCase):
    def test_consistent_counts(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        store.append_lifecycle(
            run_id="r",
            pr_number=5,
            branch="b",
            from_state="BLOCKED",
            to_state="BLOCKED",
            action="admission_denied",
            result="blocked",
        )
        out = verify_pr_rollup_consistency(store, 5)
        self.assertTrue(out["consistent"])


if __name__ == "__main__":
    unittest.main()
