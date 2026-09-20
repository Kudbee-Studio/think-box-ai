"""Pipeline v3: profiles, audit verify, idempotency, anomalies, policy waiver."""

from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_anomaly import detect_denial_anomalies
from thinkbox.pipeline_audit_packet import build_founder_audit_packet
from thinkbox.pipeline_audit_verify import verify_audit_packet
from thinkbox.pipeline_dashboard import (
    build_hermetic_pipeline_dashboard,
    compute_founder_merge_proof,
)
from thinkbox.pipeline_idempotency import find_merge_idempotency_receipt
from thinkbox.pipeline_merge_policy import evaluate_merge_policy
from thinkbox.pipeline_policy_profiles import resolve_merge_policy_for_branch
from thinkbox.pipeline_waiver import PolicyWaiverService, has_active_policy_waiver


def _seed_partial_readiness(store: OrgMemoryReceiptStore, pr: int, branch: str) -> None:
    """Score ~85: no verified evidence label on lifecycle receipt."""
    store.append_lifecycle(
        run_id=f"run_{pr}",
        pr_number=pr,
        branch=branch,
        from_state="LEARN",
        to_state="LEARN",
        action="lifecycle_complete",
        result="success",
        evidence_label="simulated",
    )


class TestPolicyProfiles(unittest.TestCase):
    def test_hotfix_lowers_readiness_threshold(self) -> None:
        pol = resolve_merge_policy_for_branch("hotfix/critical")
        self.assertEqual(pol.require_readiness_score, 80)

    def test_hotfix_branch_allows_partial_readiness_merge(self) -> None:
        aggregator, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        pr = 920
        _seed_partial_readiness(store, pr, "hotfix/critical")
        proof = compute_founder_merge_proof(pr, proof_key)
        result = merge_svc.request_merge(
            pr,
            branch="hotfix/critical",
            governance_token=token,
            founder_proof=proof,
        )
        self.assertTrue(result.admitted, result.detail)

    def test_feat_branch_still_blocks_partial_readiness(self) -> None:
        aggregator, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        pr = 921
        _seed_partial_readiness(store, pr, "feat/x")
        proof = compute_founder_merge_proof(pr, proof_key)
        result = merge_svc.request_merge(
            pr,
            branch="feat/x",
            governance_token=token,
            founder_proof=proof,
        )
        self.assertFalse(result.admitted)
        self.assertEqual(result.receipt_action, "merge_policy_denied")


class TestAuditVerify(unittest.TestCase):
    def test_verify_valid_packet(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        pkt = build_founder_audit_packet(aggregator, 930, attestation_key="v3-audit")
        out = verify_audit_packet(pkt, attestation_key="v3-audit")
        self.assertTrue(out["verified"])

    def test_verify_tampered_packet_rejected(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        pkt = build_founder_audit_packet(aggregator, 931, attestation_key="v3-audit")
        pkt["pr_number"] = 999
        out = verify_audit_packet(pkt, attestation_key="v3-audit")
        self.assertFalse(out["verified"])


class TestMergeIdempotencyKey(unittest.TestCase):
    def test_client_key_replays_without_second_receipt(self) -> None:
        aggregator, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        pr = 940
        store.append_lifecycle(
            run_id="run_940",
            pr_number=pr,
            branch="feat/x",
            from_state="LEARN",
            to_state="LEARN",
            action="lifecycle_complete",
            result="success",
            evidence_label="verified",
        )
        proof = compute_founder_merge_proof(pr, proof_key)
        first = merge_svc.request_merge(
            pr,
            governance_token=token,
            founder_proof=proof,
            idempotency_key="idem-940",
        )
        second = merge_svc.request_merge(
            pr,
            governance_token=token,
            founder_proof=proof,
            idempotency_key="idem-940",
        )
        self.assertTrue(first.admitted)
        self.assertTrue(second.idempotent)
        self.assertEqual(second.detail, "idempotency_replay")
        found = find_merge_idempotency_receipt(store, pr, "idem-940")
        self.assertIsNotNone(found)
        queued = [r for r in store.query(pr_number=pr, limit=20) if r.get("action") == "founder_merge_requested"]
        self.assertEqual(len(queued), 1)


class TestDenialAnomalies(unittest.TestCase):
    def test_spike_detected(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        for i in range(10):
            store.append_lifecycle(
                run_id="baseline",
                pr_number=700 + i,
                branch="b",
                from_state="LEARN",
                to_state="LEARN",
                action="lifecycle_complete",
                result="success",
            )
        for i in range(5):
            store.append_lifecycle(
                run_id="spike",
                pr_number=800 + i,
                branch="b",
                from_state="BLOCKED",
                to_state="BLOCKED",
                action="admission_denied",
                result="blocked",
                evidence={"admission_reason": "test"},
            )
        report = detect_denial_anomalies(store, window=5, spike_ratio=2.5, min_denials=3)
        self.assertTrue(report["anomalous"])


class TestPolicyWaiver(unittest.TestCase):
    def test_waiver_bypasses_readiness_policy(self) -> None:
        aggregator, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        gate = merge_svc._gate  # noqa: SLF001
        agent_id = merge_svc._agent_id  # noqa: SLF001
        waiver_svc = PolicyWaiverService(store, gate, agent_id)
        pr = 950
        _seed_partial_readiness(store, pr, "feat/block")
        waiver = waiver_svc.grant_waiver(pr, branch="feat/block", governance_token=token)
        self.assertTrue(waiver["granted"])
        self.assertTrue(has_active_policy_waiver(store, pr))
        pol = evaluate_merge_policy(aggregator, pr)
        self.assertFalse(pol.allowed)
        proof = compute_founder_merge_proof(pr, proof_key)
        result = merge_svc.request_merge(
            pr,
            branch="feat/block",
            governance_token=token,
            founder_proof=proof,
        )
        self.assertTrue(result.admitted, result.detail)


if __name__ == "__main__":
    unittest.main()
