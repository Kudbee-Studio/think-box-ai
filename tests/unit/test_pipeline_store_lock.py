from __future__ import annotations

import threading
import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_store_lock import serialized_org_memory_write


class TestStoreLock(unittest.TestCase):
    def test_serialized_writes(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        errors: list[str] = []

        def writer(n: int) -> None:
            try:
                with serialized_org_memory_write():
                    store.append_lifecycle(
                        run_id=f"r{n}",
                        pr_number=n,
                        branch="b",
                        from_state="A",
                        to_state="B",
                        action="act",
                        result="success",
                    )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(store.count(), 5)


if __name__ == "__main__":
    unittest.main()
