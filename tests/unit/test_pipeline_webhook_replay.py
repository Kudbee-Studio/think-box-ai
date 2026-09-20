from __future__ import annotations

import os
import tempfile
import threading
import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_webhook_replay import (
    delivery_id_fingerprint,
    register_delivery,
    reset_replay_cache,
)


class TestWebhookReplay(unittest.TestCase):
    def setUp(self) -> None:
        reset_replay_cache()

    def test_duplicate_delivery_suppressed_in_memory(self) -> None:
        self.assertTrue(register_delivery("d1"))
        self.assertFalse(register_delivery("d1"))

    def test_persisted_duplicate_after_restart_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "org.db")
            store_a = OrgMemoryReceiptStore(path)
            self.assertTrue(register_delivery("gh-delivery-1", store=store_a))
            store_a.close()
            reset_replay_cache()
            store_b = OrgMemoryReceiptStore(path)
            self.assertFalse(register_delivery("gh-delivery-1", store=store_b))
            fp = delivery_id_fingerprint("gh-delivery-1")
            rows = store_b.query_by_action("pipeline_webhook_delivery", limit=5)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["evidence"].get("delivery_id_fingerprint"), fp)
            self.assertNotIn("gh-delivery-1", str(rows[0]["evidence"]))

    def test_concurrent_duplicate_delivery_single_receipt(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        results: list[bool] = []

        def once() -> None:
            results.append(register_delivery("concurrent-d", store=store))

        threads = [threading.Thread(target=once) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(1 for r in results if r), 1)
        self.assertEqual(store.count(), 1)


if __name__ == "__main__":
    unittest.main()
