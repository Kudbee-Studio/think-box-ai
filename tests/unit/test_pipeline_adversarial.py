"""Adversarial pipeline merge-gate tests."""

from __future__ import annotations

import unittest

from thinkbox.admission import AdmissionGate
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    PIPELINE_FOUNDER_MERGE_CAPABILITY,
    FounderGatedMergeService,
    PipelineDashboardAggregator,
    compute_founder_merge_proof,
)
from thinkbox.pr_lifecycle_event_hooks import PRLifecycleEventCoordinator


class TestPipelineAdversarial(unittest.TestCase):
    def _svc(self) -> tuple[FounderGatedMergeService, str, str, str]:
        store = OrgMemoryReceiptStore(":memory:")
        coordinator = PRLifecycleEventCoordinator(store, test_mode=True)
        tokens = GovernanceTokenService(signing_key="adv-key")
        identities = IdentityLedger()
        agent_id = "pipeline-founder-gate"
        identities.register(agent_id=agent_id, capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY])
        forged = tokens.issue(
            TokenRequest(agent_id="other-agent", capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY])
        )
        valid = tokens.issue(
            TokenRequest(agent_id=agent_id, capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY])
        )
        gate = AdmissionGate(tokens, identities)
        aggregator = PipelineDashboardAggregator(store)
        proof_key = "proof-key"
        merge_svc = FounderGatedMergeService(
            store,
            gate,
            coordinator,
            agent_id=agent_id,
            founder_proof_key=proof_key,
            aggregator=aggregator,
        )
        return merge_svc, forged.token_value, valid.token_value, proof_key

    def test_forged_governance_token_denied(self) -> None:
        merge_svc, forged, _valid, proof_key = self._svc()
        proof = compute_founder_merge_proof(901, proof_key)
        result = merge_svc.request_merge(901, governance_token=forged, founder_proof=proof)
        self.assertFalse(result.admitted)
        self.assertEqual(result.detail, "token_agent_mismatch")

    def test_replay_fingerprint_without_idem_still_idempotent_queue(self) -> None:
        merge_svc, _f, valid, proof_key = self._svc()
        proof = compute_founder_merge_proof(903, proof_key)
        merge_svc.request_merge(903, governance_token=valid, founder_proof=proof)
        second = merge_svc.request_merge(903, governance_token=valid, founder_proof=proof)
        self.assertFalse(second.github_merge_called)
        self.assertIn(
            second.detail,
            (
                "already_queued",
                "replay_guard_hit",
                "idempotency_replay",
                "policy_readiness_below_threshold",
            ),
        )

    def test_missing_gate_identity_denied(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        coordinator = PRLifecycleEventCoordinator(store, test_mode=True)
        tokens = GovernanceTokenService(signing_key="adv2")
        gate = AdmissionGate(tokens, IdentityLedger())
        merge_svc = FounderGatedMergeService(
            store,
            gate,
            coordinator,
            founder_proof_key="pk",
            aggregator=PipelineDashboardAggregator(store),
        )
        issued = tokens.issue(TokenRequest(agent_id="pipeline-founder-gate", capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY]))
        proof = compute_founder_merge_proof(902, "pk")
        result = merge_svc.request_merge(902, governance_token=issued.token_value, founder_proof=proof)
        self.assertFalse(result.admitted)

    def test_double_request_merge_idempotent(self) -> None:
        merge_svc, _forged, valid, proof_key = self._svc()
        store = merge_svc._store  # noqa: SLF001
        store.append_lifecycle(
            run_id="run_903",
            pr_number=903,
            branch="feat/x",
            from_state="LEARN",
            to_state="LEARN",
            action="lifecycle_complete",
            result="success",
            evidence_label="verified",
        )
        store.append_lifecycle(
            run_id="run_903",
            pr_number=903,
            branch="feat/x",
            from_state="LEARN",
            to_state="LEARN",
            action="ci_status_observed",
            result="success",
            evidence_label="verified",
            evidence={"workflow": "unittest", "conclusion": "success", "ci_run_id": "1"},
        )
        proof = compute_founder_merge_proof(903, proof_key)
        first = merge_svc.request_merge(903, governance_token=valid, founder_proof=proof)
        second = merge_svc.request_merge(903, governance_token=valid, founder_proof=proof)
        self.assertTrue(first.admitted)
        self.assertTrue(second.admitted)
        self.assertTrue(second.idempotent)
        rows = merge_svc._store.query(pr_number=903, limit=20)  # noqa: SLF001
        queued = [r for r in rows if r.get("action") == "founder_merge_requested"]
        self.assertEqual(len(queued), 1)


if __name__ == "__main__":
    unittest.main()
