"""Hermetic tests: pipeline dashboard rollup + founder-gated merge requests."""

from __future__ import annotations

import json
import unittest

from thinkbox.github_webhook import build_hermetic_github_webhook_service, compute_github_signature
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    build_hermetic_pipeline_dashboard,
    compute_founder_merge_proof,
    summarize_pr_from_receipts,
)
from thinkbox.pr_lifecycle_event_hooks import (
    CIStatusEvent,
    GitHubPREvent,
    HermeticCIStatusEventSource,
    HermeticGitHubPREventSource,
    PRLifecycleEventCoordinator,
)


class TestPipelineRollup(unittest.TestCase):
    def test_summarize_counts_and_blocked_reasons(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        store.append_lifecycle(
            run_id="run_108",
            pr_number=108,
            branch="feat/pipeline-dashboard-admission-merge-gate",
            from_state="PR_CREATED",
            to_state="IDENTIFY",
            action="lifecycle_start",
            result="success",
            evidence_label="verified",
        )
        store.append_lifecycle(
            run_id="run_108",
            pr_number=108,
            branch="feat/pipeline-dashboard-admission-merge-gate",
            from_state="IDENTIFY",
            to_state="IDENTIFY",
            action="ci_status_observed",
            result="success",
            evidence_label="verified",
            evidence={"workflow": "unittest", "conclusion": "success", "ci_run_id": "1"},
        )
        store.append_lifecycle(
            run_id="webhook_blocked_108",
            pr_number=108,
            branch="feat/pipeline-dashboard-admission-merge-gate",
            from_state="BLOCKED",
            to_state="BLOCKED",
            action="admission_denied",
            result="blocked",
            evidence_label="simulated",
            evidence={"admission_reason": "capability_not_granted"},
        )
        receipts = store.query(pr_number=108, limit=50)
        summary = summarize_pr_from_receipts(108, receipts)
        self.assertEqual(summary.evidence_counts.verified, 2)
        self.assertEqual(summary.evidence_counts.simulated, 1)
        self.assertEqual(summary.admission_denied_count, 1)
        self.assertIsNotNone(summary.last_ci)
        self.assertIn("capability_not_granted", summary.blocked_reasons)

    def test_aggregator_overview(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        store.append_lifecycle(
            run_id="r1",
            pr_number=201,
            branch="b1",
            from_state="A",
            to_state="B",
            action="act",
            result="success",
            evidence_label="rejected",
        )
        overview = aggregator.overview()
        self.assertEqual(overview["pr_count"], 1)
        self.assertEqual(overview["totals"]["evidence_counts"]["rejected"], 1)
        self.assertFalse(overview["auto_merge"])
        self.assertTrue(overview["chain_verified"])


class TestFounderGatedMerge(unittest.TestCase):
    def test_admitted_queues_without_github_merge(self) -> None:
        aggregator, merge_svc, token, proof_key = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        store.append_lifecycle(
            run_id="run_301",
            pr_number=301,
            branch="feat/x",
            from_state="LEARN",
            to_state="LEARN",
            action="lifecycle_complete",
            result="success",
            evidence_label="verified",
        )
        store.append_lifecycle(
            run_id="run_301",
            pr_number=301,
            branch="feat/x",
            from_state="LEARN",
            to_state="LEARN",
            action="ci_status_observed",
            result="success",
            evidence_label="verified",
            evidence={"workflow": "unittest", "conclusion": "success", "ci_run_id": "1"},
        )
        proof = compute_founder_merge_proof(301, proof_key)
        result = merge_svc.request_merge(301, governance_token=token, founder_proof=proof)
        self.assertTrue(result.admitted)
        self.assertFalse(result.merged)
        self.assertFalse(result.github_merge_called)
        self.assertEqual(result.receipt_action, "founder_merge_requested")
        self.assertTrue(result.receipt_proof_hash)
        detail = aggregator.pr_detail(301)
        self.assertEqual(detail["summary"]["merge_request_status"], "queued")

    def test_missing_proof_denied_with_matrix(self) -> None:
        _, merge_svc, token, _ = build_hermetic_pipeline_dashboard()
        result = merge_svc.request_merge(305, governance_token=token, founder_proof="")
        self.assertFalse(result.admitted)
        self.assertEqual(result.http_status, 403)
        checks = {row["check"] for row in result.deny_matrix}
        self.assertIn("founder_merge_proof", checks)

    def test_invalid_token_denied_with_receipt(self) -> None:
        aggregator, merge_svc, _, proof_key = build_hermetic_pipeline_dashboard()
        proof = compute_founder_merge_proof(302, proof_key)
        result = merge_svc.request_merge(302, governance_token="not-a-real-token", founder_proof=proof)
        self.assertFalse(result.admitted)
        self.assertEqual(result.http_status, 403)
        receipts = aggregator._store.query(pr_number=302, limit=10)  # noqa: SLF001
        self.assertTrue(any(r.get("action") == "merge_request_denied" for r in receipts))

    def test_webhook_and_pipeline_share_store_pattern(self) -> None:
        """Webhook admissions + pipeline rollup compose on one org-memory store."""
        store = OrgMemoryReceiptStore(":memory:")
        coord = PRLifecycleEventCoordinator(store, test_mode=True)
        gh_svc = build_hermetic_github_webhook_service("whsec-test")
        gh_svc._store = store  # noqa: SLF001
        gh_svc._coordinator = coord  # noqa: SLF001

        aggregator, merge_svc, founder_token, proof_key = build_hermetic_pipeline_dashboard()
        aggregator._store = store  # noqa: SLF001
        merge_svc._store = store  # noqa: SLF001
        merge_svc._coordinator = coord  # noqa: SLF001

        payload = {
            "action": "opened",
            "number": 401,
            "pull_request": {"head": {"ref": "feat/pipeline", "sha": "abc"}},
        }
        body = json.dumps(payload).encode()
        sig = compute_github_signature("whsec-test", body)
        wh = gh_svc.process(body, "pull_request", sig)
        self.assertTrue(wh.admission_allowed)

        ci = HermeticCIStatusEventSource()
        gh = HermeticGitHubPREventSource()
        ci.push(CIStatusEvent(pr_number=401, workflow="unittest", conclusion="success"))
        coord.drain_sources(gh, ci)

        overview = aggregator.overview()
        self.assertGreaterEqual(overview["pr_count"], 1)
        proof = compute_founder_merge_proof(401, proof_key)
        merge = merge_svc.request_merge(401, governance_token=founder_token, founder_proof=proof)
        self.assertTrue(merge.admitted)
        self.assertFalse(merge.github_merge_called)


class TestDistinctPrNumbers(unittest.TestCase):
    def test_distinct_pr_numbers_ordered(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        for pr in (3, 1, 2):
            store.append_lifecycle(
                run_id=f"r{pr}",
                pr_number=pr,
                branch="b",
                from_state="A",
                to_state="B",
                action="act",
                result="success",
            )
        self.assertEqual(store.distinct_pr_numbers(), [1, 2, 3])


class TestAdmissionDenialLedger(unittest.TestCase):
    def test_denial_aggregation_by_reason(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        for reason in ("capability_not_granted", "capability_not_granted", "signature_mismatch"):
            store.append_lifecycle(
                run_id="wb",
                pr_number=501,
                branch="b",
                from_state="BLOCKED",
                to_state="BLOCKED",
                action="admission_denied",
                result="blocked",
                evidence={"admission_reason": reason},
            )
        ledger = aggregator.admission_denial_ledger(receipt_limit=100)
        self.assertEqual(ledger["total_denials"], 3)
        self.assertEqual(ledger["by_reason"]["capability_not_granted"], 2)
        self.assertEqual(ledger["by_reason"]["signature_mismatch"], 1)


class TestPrReceiptIntegrity(unittest.TestCase):
    def test_integrity_reports_chain_and_hashes(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        store.append_lifecycle(
            run_id="r",
            pr_number=601,
            branch="b",
            from_state="A",
            to_state="B",
            action="act",
            result="success",
            evidence_label="verified",
        )
        report = aggregator.verify_pr_receipt_integrity(601)
        self.assertTrue(report["chain_verified"])
        self.assertEqual(report["receipt_count"], 1)
        self.assertTrue(report["first_entry_hash"])


class TestCITimeline(unittest.TestCase):
    def test_ci_timeline_chronological(self) -> None:
        aggregator, _, _, _ = build_hermetic_pipeline_dashboard()
        store = aggregator._store  # noqa: SLF001
        for wf, conclusion in (("unittest", "failure"), ("unittest", "success")):
            store.append_lifecycle(
                run_id="r",
                pr_number=602,
                branch="b",
                from_state="A",
                to_state="A",
                action="ci_status_observed",
                result="success",
                evidence={"workflow": wf, "conclusion": conclusion, "ci_run_id": conclusion},
            )
        timeline = aggregator.ci_status_timeline(602)
        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[0]["conclusion"], "failure")
        self.assertEqual(timeline[1]["conclusion"], "success")


class TestPipelineQuarantine(unittest.TestCase):
    def test_quarantine_toggle_requires_token(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        from thinkbox.admission import AdmissionGate
        from thinkbox.governance_token import GovernanceTokenService, TokenRequest
        from thinkbox.identity import IdentityLedger
        from thinkbox.pipeline_dashboard import PipelineQuarantineController

        agent_id = "pipeline-founder-gate"
        tokens = GovernanceTokenService(signing_key="q-key")
        identities = IdentityLedger()
        identities.register(agent_id=agent_id, capabilities=[PipelineQuarantineController.QUARANTINE_CAPABILITY])
        issued = tokens.issue(
            TokenRequest(agent_id=agent_id, capabilities=[PipelineQuarantineController.QUARANTINE_CAPABILITY])
        )
        gate = AdmissionGate(tokens, identities)
        ctrl = PipelineQuarantineController(store, gate, agent_id=agent_id)
        denied = ctrl.set_quarantine(quarantined=True, reason="test", governance_token="bad")
        self.assertFalse(denied["admitted"])
        ok = ctrl.set_quarantine(quarantined=True, reason="test", governance_token=issued.token_value)
        self.assertTrue(ok["admitted"])
        self.assertTrue(ctrl.read()["quarantined"])


if __name__ == "__main__":
    unittest.main()
