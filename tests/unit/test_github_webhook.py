"""Hermetic tests for GitHub webhook signature verification and lifecycle dispatch."""

from __future__ import annotations

import json
import os
import unittest

from thinkbox.github_webhook import (
    build_hermetic_github_webhook_service,
    compute_github_signature,
    parse_github_webhook_payload,
    verify_github_webhook_signature,
)
from thinkbox.pr_lifecycle import PRLifecycleState

_HERMETIC_SECRET = "hermetic-webhook-secret-7bd0"


def _signed_body(secret: str, payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode("utf-8")
    return body, compute_github_signature(secret, body)


class TestGitHubWebhookSignature(unittest.TestCase):
    def test_valid_hmac_accepted(self) -> None:
        body, sig = _signed_body(_HERMETIC_SECRET, {"zen": "test"})
        result = verify_github_webhook_signature(_HERMETIC_SECRET, body, sig)
        self.assertTrue(result.valid)
        self.assertEqual(result.evidence_label, "verified")

    def test_forged_hmac_rejected(self) -> None:
        body = b'{"action":"opened"}'
        result = verify_github_webhook_signature(
            _HERMETIC_SECRET,
            body,
            "sha256=deadbeef",
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.evidence_label, "rejected")

    def test_missing_signature_fail_closed(self) -> None:
        result = verify_github_webhook_signature(_HERMETIC_SECRET, b"{}", None)
        self.assertFalse(result.valid)
        self.assertIn("missing", result.reason)

    def test_missing_secret_fail_closed(self) -> None:
        body, sig = _signed_body(_HERMETIC_SECRET, {})
        result = verify_github_webhook_signature("", body, sig)
        self.assertFalse(result.valid)


class TestGitHubWebhookParsing(unittest.TestCase):
    def test_pull_request_open_maps_to_github_event(self) -> None:
        payload = {
            "action": "opened",
            "number": 109,
            "pull_request": {
                "head": {"ref": "feat/lifecycle-github-webhook-admission", "sha": "abc"},
            },
        }
        items = parse_github_webhook_payload("pull_request", payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].kind, "github_pr")
        assert items[0].event is not None
        self.assertEqual(items[0].event.pr_number, 109)
        self.assertEqual(items[0].event.action, "opened")

    def test_workflow_run_completed_maps_ci(self) -> None:
        payload = {
            "action": "completed",
            "workflow": {"name": "unittest"},
            "workflow_run": {
                "id": 99,
                "conclusion": "success",
                "pull_requests": [{"number": 109}],
            },
        }
        items = parse_github_webhook_payload("workflow_run", payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].kind, "ci_status")
        assert items[0].event is not None
        self.assertEqual(items[0].event.conclusion, "success")


class TestGitHubWebhookLifecycleService(unittest.TestCase):
    def _service(self) -> tuple:
        svc = build_hermetic_github_webhook_service(_HERMETIC_SECRET)
        store = svc._store  # noqa: SLF001 — test inspects receipt chain
        return svc, store

    def test_bad_signature_no_mutation(self) -> None:
        svc, store = self._service()
        before = store.count()
        result = svc.process(b"{}", "pull_request", "sha256=invalid")
        self.assertEqual(result.http_status, 401)
        self.assertFalse(result.signature_valid)
        self.assertEqual(store.count(), before)

    def test_verified_open_ci_success_never_merge(self) -> None:
        svc, store = self._service()
        open_payload = {
            "action": "opened",
            "number": 109,
            "pull_request": {
                "head": {"ref": "feat/lifecycle-github-webhook-admission", "sha": "abc"},
            },
        }
        body, sig = _signed_body(_HERMETIC_SECRET, open_payload)
        open_result = svc.process(body, "pull_request", sig)
        self.assertEqual(open_result.http_status, 200)
        self.assertEqual(open_result.evidence_label, "verified")

        ci_payload = {
            "action": "completed",
            "workflow": {"name": "unittest"},
            "workflow_run": {
                "id": 1,
                "conclusion": "success",
                "pull_requests": [{"number": 109}],
            },
        }
        ci_body, ci_sig = _signed_body(_HERMETIC_SECRET, ci_payload)
        ci_result = svc.process(ci_body, "workflow_run", ci_sig)
        self.assertTrue(any(o.get("terminal_state") == PRLifecycleState.LEARN.value for o in ci_result.outcomes))
        merge = svc._coordinator.request_merge(109)  # noqa: SLF001
        self.assertFalse(merge["merged"])
        receipts = store.query(pr_number=109, limit=50)
        self.assertTrue(any(r["evidence_label"] == "verified" for r in receipts))
        self.assertTrue(store.verify())

    def test_admission_denied_writes_blocked_receipt(self) -> None:
        from thinkbox.github_webhook import GitHubWebhookLifecycleService
        from thinkbox.admission import AdmissionGate
        from thinkbox.governance_token import GovernanceTokenService
        from thinkbox.identity import IdentityLedger
        from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
        from thinkbox.pr_lifecycle_event_hooks import PRLifecycleEventCoordinator
        from thinkbox.github_webhook import GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY, DEFAULT_WEBHOOK_AGENT_ID

        store = OrgMemoryReceiptStore(":memory:")
        coordinator = PRLifecycleEventCoordinator(store, test_mode=True)
        tokens = GovernanceTokenService(signing_key="deny-key")
        identities = IdentityLedger()
        identities.register(
            agent_id=DEFAULT_WEBHOOK_AGENT_ID,
            capabilities=[GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY],
        )
        gate = AdmissionGate(tokens, identities)
        svc = GitHubWebhookLifecycleService(
            webhook_secret=_HERMETIC_SECRET,
            store=store,
            coordinator=coordinator,
            gate=gate,
            governance_token="invalid-token",
            agent_id=DEFAULT_WEBHOOK_AGENT_ID,
        )
        payload = {
            "action": "opened",
            "number": 110,
            "pull_request": {"head": {"ref": "b", "sha": "x"}},
        }
        body, sig = _signed_body(_HERMETIC_SECRET, payload)
        result = svc.process(body, "pull_request", sig)
        self.assertEqual(result.http_status, 403)
        self.assertFalse(result.admission_allowed)
        blocked = store.query(pr_number=110, limit=5)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["to_state"], "BLOCKED")
        self.assertEqual(blocked[0]["result"], "blocked")


class TestGitHubWebhookReplay(unittest.TestCase):
    def test_duplicate_delivery_suppressed(self) -> None:
        from thinkbox.pipeline_webhook_replay import reset_replay_cache

        reset_replay_cache()
        svc = build_hermetic_github_webhook_service(_HERMETIC_SECRET)
        payload = {"zen": "replay-test"}
        body, sig = _signed_body(_HERMETIC_SECRET, payload)
        first = svc.process(body, "ping", sig, delivery_id="delivery-abc")
        second = svc.process(body, "ping", sig, delivery_id="delivery-abc")
        self.assertEqual(first.detail, "ping")
        self.assertEqual(second.detail, "delivery_replay_suppressed")


@unittest.skipUnless(
    os.getenv("THINKBOX_GITHUB_WEBHOOK_LIVE_TEST", "").lower() in ("1", "true", "yes")
    and bool(os.getenv("WEBHOOK_SECRET") or os.getenv("GITHUB_WEBHOOK_SECRET")),
    "live webhook test disabled (set THINKBOX_GITHUB_WEBHOOK_LIVE_TEST=1 and WEBHOOK_SECRET)",
)
class TestGitHubWebhookLiveOptional(unittest.TestCase):
    def test_live_secret_roundtrip(self) -> None:
        secret = os.getenv("WEBHOOK_SECRET") or os.getenv("GITHUB_WEBHOOK_SECRET") or ""
        body = b'{"live": true}'
        sig = compute_github_signature(secret, body)
        self.assertTrue(verify_github_webhook_signature(secret, body, sig).valid)


if __name__ == "__main__":
    unittest.main()
