from __future__ import annotations

import threading
import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import build_hermetic_pipeline_dashboard, compute_founder_merge_proof


class TestWriterConcurrency(unittest.TestCase):
    def test_concurrent_merge_denials_remain_consistent(self) -> None:
        agg, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store: OrgMemoryReceiptStore = agg._store  # noqa: SLF001
        errors: list[str] = []

        def deny_once(pr: int) -> None:
            try:
                merge_svc.request_merge(
                    pr,
                    governance_token="not-a-real-token",
                    founder_proof=compute_founder_merge_proof(pr, proof_key),
                )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=deny_once, args=(3000 + i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertTrue(store.verify())
        denied = [r for r in store.query_by_action("merge_request_denied", limit=50)]
        self.assertGreaterEqual(len(denied), 8)


if __name__ == "__main__":
    unittest.main()
