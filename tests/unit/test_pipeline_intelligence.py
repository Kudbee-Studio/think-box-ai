"""Tests for pipeline intelligence layer (readiness, audit, policy, correlation, checkpoint)."""

from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_audit_packet import attest_audit_packet, build_founder_audit_packet
from thinkbox.pipeline_correlation import compute_blast_radius
from thinkbox.pipeline_dashboard import (
    PipelineDashboardAggregator,
    build_hermetic_pipeline_dashboard,
    compute_founder_merge_proof,
)
from thinkbox.pipeline_fleet_checkpoint import FleetCheckpointService
from thinkbox.pipeline_readiness import evaluate_merge_readiness


def _seed_merge_ready(store: OrgMemoryReceiptStore, pr: int) -> None:
    store.append_lifecycle(
        run_id=f"run_{pr}",
        pr_number=pr,
        branch="feat/x",
        from_state="LEARN",
        to_state="LEARN",
        action="lifecycle_complete",
        result="success",
        evidence_label="verified",
    )
    store.append_lifecycle(
        run_id=f"run_{pr}",
        pr_number=pr,
        branch="feat/x",
        from_state="LEARN",
        to_state="LEARN",
        action="ci_status_observed",
        result="success",
        evidence_label="verified",
        evidence={"workflow": "unittest", "conclusion": "success", "ci_run_id": "1"},
    )


class TestMergeReadiness(unittest.TestCase):
    def test_full_score_when_gates_pass(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        _seed_merge_ready(aggregator._store, 901)  # noqa: SLF001
        report = evaluate_merge_readiness(aggregator._store, 901)  # noqa: SLF001
        self.assertTrue(report.ready)
        self.assertEqual(report.score, 100)

    def test_blockers_when_ci_missing(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        store.append_lifecycle(
            run_id="r",
            pr_number=902,
            branch="b",
            from_state="A",
            to_state="B",
            action="act",
            result="success",
            evidence_label="verified",
        )
        report = evaluate_merge_readiness(store, 902)
        self.assertTrue(report.ready)
        self.assertEqual(report.score, 100)

    def test_explicit_ci_failure_blocks(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        store.append_lifecycle(
            run_id="r",
            pr_number=906,
            branch="b",
            from_state="A",
            to_state="B",
            action="act",
            result="success",
            evidence_label="verified",
        )
        store.append_lifecycle(
            run_id="r",
            pr_number=906,
            branch="b",
            from_state="A",
            to_state="A",
            action="ci_status_observed",
            result="success",
            evidence={"workflow": "unittest", "conclusion": "failure"},
        )
        report = evaluate_merge_readiness(store, 906)
        self.assertFalse(report.ready)


class TestMergeWithoutCiReceipt(unittest.TestCase):
    def test_request_merge_without_ci_observation(self) -> None:
        aggregator, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        store.append_lifecycle(
            run_id="run_local",
            pr_number=907,
            branch="feat/local-gate",
            from_state="LEARN",
            to_state="LEARN",
            action="lifecycle_complete",
            result="success",
            evidence_label="verified",
        )
        proof = compute_founder_merge_proof(907, proof_key)
        result = merge_svc.request_merge(907, governance_token=token, founder_proof=proof)
        self.assertTrue(result.admitted)
        self.assertEqual(result.receipt_action, "founder_merge_requested")


class TestAuditPacket(unittest.TestCase):
    def test_attestation_stable(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        _seed_merge_ready(aggregator._store, 903)  # noqa: SLF001
        pkt = build_founder_audit_packet(aggregator, 903, attestation_key="audit-key")
        self.assertTrue(pkt["attestation"])
        body = dict(pkt)
        att = body.pop("attestation")
        self.assertEqual(att, attest_audit_packet(body, "audit-key"))


class TestMergePolicyIntegration(unittest.TestCase):
    def test_policy_blocks_without_verified_evidence(self) -> None:
        aggregator, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        proof = compute_founder_merge_proof(904, proof_key)
        result = merge_svc.request_merge(904, governance_token=token, founder_proof=proof)
        self.assertFalse(result.admitted)
        self.assertEqual(result.receipt_action, "merge_policy_denied")


class TestBlastRadius(unittest.TestCase):
    def test_clusters_shared_denial_reason(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        for pr in (911, 912):
            store.append_lifecycle(
                run_id="wb",
                pr_number=pr,
                branch=f"feat/{pr}",
                from_state="BLOCKED",
                to_state="BLOCKED",
                action="admission_denied",
                result="blocked",
                evidence={"admission_reason": "capability_not_granted"},
            )
        radius = compute_blast_radius(aggregator)
        self.assertTrue(any(h["key"] == "capability_not_granted" for h in radius["hotspots"]))


class TestFleetCheckpoint(unittest.TestCase):
    def test_create_and_verify_checkpoint(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        svc = FleetCheckpointService(aggregator._store, aggregator)  # noqa: SLF001
        cp = svc.create_checkpoint()
        verify = svc.verify_latest()
        self.assertTrue(verify["verified"])
        self.assertEqual(cp.chain_head_hash, verify["checkpoint"]["chain_head_hash"])


if __name__ == "__main__":
    unittest.main()
