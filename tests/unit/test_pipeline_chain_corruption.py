"""Receipt-chain corruption detection tests."""

from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore


class TestChainCorruption(unittest.TestCase):
    def test_tampered_hash_breaks_verify(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        store.append_lifecycle(
            run_id="r",
            pr_number=1,
            branch="b",
            from_state="A",
            to_state="B",
            action="act",
            result="success",
        )
        self.assertTrue(store.verify())
        with store._lock:  # noqa: SLF001
            store._conn.execute(
                "UPDATE org_lifecycle_receipts SET entry_hash = 'tampered' WHERE sequence = 1"
            )
            store._conn.commit()
        self.assertFalse(store.verify())


if __name__ == "__main__":
    unittest.main()
