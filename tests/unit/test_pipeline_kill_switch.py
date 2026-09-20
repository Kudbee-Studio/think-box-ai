from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    PipelineQuarantineController,
    build_hermetic_pipeline_dashboard,
    compute_founder_merge_proof,
)


class TestKillSwitch(unittest.TestCase):
    def test_quarantine_blocks_merge(self) -> None:
        agg, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store = agg._store  # noqa: SLF001
        q = PipelineQuarantineController(store, merge_svc._gate, agent_id=merge_svc._agent_id)  # noqa: SLF001
        q.set_quarantine(quarantined=True, reason="test", governance_token=token)
        pr = 909
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
