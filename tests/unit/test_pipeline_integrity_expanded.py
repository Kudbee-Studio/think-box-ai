from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_integrity import expanded_pr_integrity


class TestExpandedIntegrity(unittest.TestCase):
    def test_includes_state_machine(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        store.append_lifecycle(
            run_id="r",
            pr_number=9,
            branch="b",
            from_state="A",
            to_state="LEARN",
            action="learn",
            result="success",
        )
        report = expanded_pr_integrity(store, 9)
        self.assertTrue(report["chain_verified"])
        self.assertIn("state_machine", report)


if __name__ == "__main__":
    unittest.main()
