"""End-to-end hermetic control-plane pipeline scenario."""

from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    PipelineDashboardAggregator,
    build_hermetic_pipeline_dashboard,
    compute_founder_merge_proof,
)
from thinkbox.pipeline_recovery import reconcile_overview_chain


class TestPipelineE2EHermetic(unittest.TestCase):
    def test_webhook_denial_to_founder_queue_never_merge(self) -> None:
        agg, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store: OrgMemoryReceiptStore = agg._store  # noqa: SLF001
        store.append_lifecycle(
            run_id="wh",
            pr_number=1001,
            branch="feat/e2e",
            from_state="BLOCKED",
            to_state="BLOCKED",
            action="admission_denied",
            result="blocked",
            evidence={"admission_reason": "test"},
        )
        proof = compute_founder_merge_proof(1001, proof_key)
        merge = merge_svc.request_merge(
            1001,
            governance_token=token,
            founder_proof=proof,
            branch="feat/e2e",
        )
        self.assertFalse(merge.github_merge_called)
        self.assertFalse(merge.merged)
        overview = PipelineDashboardAggregator(store).overview()
        self.assertTrue(overview["chain_verified"])
        recon = reconcile_overview_chain(store)
        self.assertTrue(recon["chain_verified"])


if __name__ == "__main__":
    unittest.main()
