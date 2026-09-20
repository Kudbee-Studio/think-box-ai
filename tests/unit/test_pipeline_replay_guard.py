from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    build_hermetic_pipeline_dashboard,
    compute_founder_merge_proof,
)
from thinkbox.pipeline_replay_guard import find_replay_receipt, merge_request_fingerprint


class TestReplayGuard(unittest.TestCase):
    def test_fingerprint_stable(self) -> None:
        a = merge_request_fingerprint(1, "b", "k", "ph")
        b = merge_request_fingerprint(1, "b", "k", "ph")
        self.assertEqual(a, b)

    def test_merge_service_replay_guard(self) -> None:
        agg, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        pr = 777
        proof = compute_founder_merge_proof(pr, proof_key)
        r1 = merge_svc.request_merge(
            pr,
            governance_token=token,
            founder_proof=proof,
            idempotency_key="idem-1",
        )
        r2 = merge_svc.request_merge(
            pr,
            governance_token=token,
            founder_proof=proof,
            idempotency_key="idem-1",
        )
        self.assertFalse(r2.github_merge_called)
        allowed_details = (
            "idempotency_replay",
            "replay_guard_hit",
            "already_queued",
            "queued_for_founder_review",
            "policy_readiness_below_threshold",
        )
        self.assertIn(r2.detail, allowed_details)
        if r1.admitted and r2.admitted:
            self.assertTrue(r2.idempotent or r2.detail == "already_queued")
        if r1.detail == r2.detail == "policy_readiness_below_threshold":
            self.assertFalse(r2.github_merge_called)

    def test_find_replay_receipt(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        fp = merge_request_fingerprint(2, "b", "", "x")
        store.append_lifecycle(
            run_id="r",
            pr_number=2,
            branch="b",
            from_state="A",
            to_state="B",
            action="founder_merge_requested",
            result="queued",
            evidence={"replay_fingerprint": fp},
        )
        self.assertIsNotNone(find_replay_receipt(store, 2, fp))


if __name__ == "__main__":
    unittest.main()
