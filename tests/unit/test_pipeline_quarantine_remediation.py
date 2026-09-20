from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    PipelineQuarantineController,
    build_hermetic_pipeline_dashboard,
    compute_founder_merge_proof,
)


class TestQuarantineActionScopedRead(unittest.TestCase):
    def test_read_survives_more_than_fifty_unrelated_receipts(self) -> None:
        agg, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store: OrgMemoryReceiptStore = agg._store  # noqa: SLF001
        q = PipelineQuarantineController(store, merge_svc._gate, agent_id=merge_svc._agent_id)  # noqa: SLF001
        q.set_quarantine(quarantined=True, reason="kill-switch", governance_token=token)
        for i in range(55):
            store.append_lifecycle(
                run_id=f"noise_{i}",
                pr_number=1000 + i,
                branch="noise",
                from_state="A",
                to_state="B",
                action="ci_status",
                result="success",
                evidence_label="simulated",
                evidence={"index": i},
            )
        state = q.read()
        self.assertTrue(state["quarantined"])
        self.assertEqual(state["reason"], "kill-switch")

    def test_request_merge_blocked_after_receipt_window_exhaustion(self) -> None:
        agg, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store: OrgMemoryReceiptStore = agg._store  # noqa: SLF001
        q = PipelineQuarantineController(store, merge_svc._gate, agent_id=merge_svc._agent_id)  # noqa: SLF001
        q.set_quarantine(quarantined=True, reason="window-test", governance_token=token)
        for i in range(60):
            store.append_lifecycle(
                run_id=f"filler_{i}",
                pr_number=2000 + i,
                branch="filler",
                from_state="IDENTIFY",
                to_state="EXECUTE",
                action="lifecycle_noise",
                result="success",
                evidence_label="simulated",
                evidence={},
            )
        pr = 1099
        proof = compute_founder_merge_proof(pr, proof_key)
        result = merge_svc.request_merge(
            pr,
            governance_token=token,
            founder_proof=proof,
            quarantine_state=q.read(),
        )
        self.assertFalse(result.admitted)
        self.assertEqual(result.detail, "pipeline_quarantined")
        self.assertFalse(result.github_merge_called)


if __name__ == "__main__":
    unittest.main()
