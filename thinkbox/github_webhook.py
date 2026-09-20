"""GitHub webhook signature verification and PR lifecycle dispatch (hermetic-safe)."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union

from thinkbox.admission import AdmissionGate, AdmissionDecision
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pr_lifecycle_event_hooks import (
    CIStatusEvent,
    GitHubPREvent,
    PRLifecycleEventCoordinator,
)

GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY = "github:webhook:lifecycle_mutate"
DEFAULT_WEBHOOK_AGENT_ID = "github-webhook-receiver"


@dataclass(frozen=True)
class SignatureVerification:
    """Outcome of X-Hub-Signature-256 validation."""

    valid: bool
    reason: str

    @property
    def evidence_label(self) -> str:
        return "verified" if self.valid else "rejected"


def compute_github_signature(secret: str, body: bytes) -> str:
    """Return the GitHub-style sha256= HMAC header value (for tests and probes)."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_github_webhook_signature(
    secret: str,
    body: bytes,
    signature_header: Optional[str],
) -> SignatureVerification:
    """Fail-closed verification of GitHub webhook HMAC (X-Hub-Signature-256)."""
    if not secret:
        return SignatureVerification(False, "webhook_secret_not_configured")
    if not signature_header:
        return SignatureVerification(False, "missing_x_hub_signature_256")
    if not signature_header.startswith("sha256="):
        return SignatureVerification(False, "invalid_signature_prefix")
    expected = compute_github_signature(secret, body)
    if not hmac.compare_digest(expected, signature_header):
        return SignatureVerification(False, "signature_mismatch")
    return SignatureVerification(True, "ok")


WebhookDispatchKind = Literal["github_pr", "ci_status", "noop"]


@dataclass(frozen=True)
class WebhookDispatchItem:
    kind: WebhookDispatchKind
    event: Union[GitHubPREvent, CIStatusEvent, None] = None
    pr_number: int = 0
    branch: str = ""


def parse_github_webhook_payload(event_type: str, payload: dict[str, Any]) -> list[WebhookDispatchItem]:
    """Map GitHub delivery event types to lifecycle coordinator inputs."""
    event_type = (event_type or "").lower()
    if event_type == "ping":
        return [WebhookDispatchItem(kind="noop")]

    if event_type == "pull_request":
        pr = payload.get("pull_request") or {}
        number = int(payload.get("number") or pr.get("number") or 0)
        head = pr.get("head") or {}
        return [
            WebhookDispatchItem(
                kind="github_pr",
                pr_number=number,
                branch=str(head.get("ref") or ""),
                event=GitHubPREvent(
                    pr_number=number,
                    branch=str(head.get("ref") or ""),
                    action=str(payload.get("action") or ""),
                    head_sha=str(head.get("sha") or ""),
                ),
            )
        ]

    if event_type == "check_suite":
        action = str(payload.get("action") or "")
        suite = payload.get("check_suite") or {}
        conclusion = str(suite.get("conclusion") or "pending")
        if action not in ("completed",) and conclusion in ("", "pending", "null"):
            return []
        workflow = str((suite.get("app") or {}).get("slug") or "check_suite")
        run_id = str(suite.get("id") or "")
        items: list[WebhookDispatchItem] = []
        for pr in suite.get("pull_requests") or []:
            num = int(pr.get("number") or 0)
            if num <= 0:
                continue
            items.append(
                WebhookDispatchItem(
                    kind="ci_status",
                    pr_number=num,
                    event=CIStatusEvent(
                        pr_number=num,
                        workflow=workflow,
                        conclusion=conclusion,
                        run_id=run_id,
                    ),
                )
            )
        return items

    if event_type == "workflow_run":
        action = str(payload.get("action") or "")
        if action not in ("completed",):
            return []
        run = payload.get("workflow_run") or {}
        conclusion = str(run.get("conclusion") or "pending")
        workflow = str((payload.get("workflow") or {}).get("name") or run.get("name") or "workflow")
        run_id = str(run.get("id") or "")
        branch = str(run.get("head_branch") or "")
        items: list[WebhookDispatchItem] = []
        for pr in run.get("pull_requests") or []:
            num = int(pr.get("number") or 0)
            if num <= 0:
                continue
            items.append(
                WebhookDispatchItem(
                    kind="ci_status",
                    pr_number=num,
                    branch=branch,
                    event=CIStatusEvent(
                        pr_number=num,
                        workflow=workflow,
                        conclusion=conclusion,
                        run_id=run_id,
                    ),
                )
            )
        return items

    if event_type == "status":
        state = str(payload.get("state") or "pending")
        sha = str(payload.get("sha") or "")
        context = str(payload.get("context") or "status")
        items: list[WebhookDispatchItem] = []
        for branch_info in payload.get("branches") or []:
            meta = branch_info if isinstance(branch_info, dict) else {}
            pr_num = int(meta.get("pr_number") or meta.get("number") or 0)
            if pr_num <= 0:
                continue
            items.append(
                WebhookDispatchItem(
                    kind="ci_status",
                    pr_number=pr_num,
                    event=CIStatusEvent(
                        pr_number=pr_num,
                        workflow=context,
                        conclusion=state,
                        run_id=sha,
                    ),
                )
            )
        return items

    return []


def infer_pr_context(payload: dict[str, Any], items: list[WebhookDispatchItem]) -> tuple[int, str]:
    """Best-effort PR number and branch for admission-denial receipts."""
    for item in items:
        if item.pr_number > 0:
            return item.pr_number, item.branch
    pr = payload.get("pull_request") or {}
    number = int(payload.get("number") or pr.get("number") or 0)
    branch = str((pr.get("head") or {}).get("ref") or "")
    return number, branch


@dataclass
class GitHubWebhookProcessResult:
    http_status: int
    evidence_label: str
    signature_valid: bool
    admission_allowed: bool
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    detail: str = ""

    def to_response_body(self) -> dict[str, Any]:
        return {
            "ok": self.http_status < 400,
            "evidence_label": self.evidence_label,
            "signature_valid": self.signature_valid,
            "admission_allowed": self.admission_allowed,
            "outcomes": self.outcomes,
            "detail": self.detail,
            "auto_merge": False,
        }


class GitHubWebhookLifecycleService:
    """Verify signatures, admit mutating lifecycle side-effects, dispatch to coordinator."""

    def __init__(
        self,
        *,
        webhook_secret: str,
        store: OrgMemoryReceiptStore,
        coordinator: PRLifecycleEventCoordinator,
        gate: AdmissionGate,
        governance_token: str,
        agent_id: str = DEFAULT_WEBHOOK_AGENT_ID,
    ) -> None:
        self._secret = webhook_secret
        self._store = store
        self._coordinator = coordinator
        self._gate = gate
        self._governance_token = governance_token
        self._agent_id = agent_id

    def process(
        self,
        body: bytes,
        event_type: str,
        signature_header: Optional[str],
        delivery_id: Optional[str] = None,
    ) -> GitHubWebhookProcessResult:
        from thinkbox.pipeline_webhook_replay import register_delivery

        if delivery_id and not register_delivery(delivery_id, store=self._store):
            return GitHubWebhookProcessResult(
                http_status=200,
                evidence_label="simulated",
                signature_valid=True,
                admission_allowed=True,
                detail="delivery_replay_suppressed",
            )

        sig = verify_github_webhook_signature(self._secret, body, signature_header)
        if not sig.valid:
            return GitHubWebhookProcessResult(
                http_status=401,
                evidence_label=sig.evidence_label,
                signature_valid=False,
                admission_allowed=False,
                detail=sig.reason,
            )

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return GitHubWebhookProcessResult(
                http_status=400,
                evidence_label="rejected",
                signature_valid=True,
                admission_allowed=False,
                detail="invalid_json_payload",
            )

        items = parse_github_webhook_payload(event_type, payload)
        if not items:
            return GitHubWebhookProcessResult(
                http_status=200,
                evidence_label="verified",
                signature_valid=True,
                admission_allowed=True,
                detail="no_dispatchable_events",
            )

        if all(item.kind == "noop" for item in items):
            return GitHubWebhookProcessResult(
                http_status=200,
                evidence_label="verified",
                signature_valid=True,
                admission_allowed=True,
                detail="ping",
            )

        decision = self._gate.authorize(
            self._governance_token,
            self._agent_id,
            GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY,
            metadata={"event_type": event_type},
        )
        if not decision.allowed:
            pr_number, branch = infer_pr_context(payload, items)
            self._record_admission_blocked(
                pr_number=pr_number,
                branch=branch,
                event_type=event_type,
                decision=decision,
            )
            return GitHubWebhookProcessResult(
                http_status=403,
                evidence_label="simulated",
                signature_valid=True,
                admission_allowed=False,
                detail=decision.reason,
            )

        outcomes: list[dict[str, Any]] = []
        for item in items:
            if item.kind == "github_pr" and isinstance(item.event, GitHubPREvent):
                outcomes.append(
                    self._coordinator.handle_github_event(
                        item.event,
                        evidence_label="verified",
                    )
                )
            elif item.kind == "ci_status" and isinstance(item.event, CIStatusEvent):
                outcomes.append(
                    self._coordinator.handle_ci_event(
                        item.event,
                        evidence_label="verified",
                    )
                )
        return GitHubWebhookProcessResult(
            http_status=200,
            evidence_label="verified",
            signature_valid=True,
            admission_allowed=True,
            outcomes=outcomes,
            detail="dispatched",
        )

    def _record_admission_blocked(
        self,
        *,
        pr_number: int,
        branch: str,
        event_type: str,
        decision: AdmissionDecision,
    ) -> None:
        run_id = f"webhook_blocked_{pr_number or 'unknown'}"
        self._store.append_lifecycle(
            run_id=run_id,
            pr_number=pr_number,
            branch=branch,
            from_state="BLOCKED",
            to_state="BLOCKED",
            action="admission_denied",
            result="blocked",
            evidence_label="simulated",
            evidence={
                "event_type": event_type,
                "admission_reason": decision.reason,
                "agent_id": decision.agent_id,
                "capability": decision.capability,
            },
        )


def build_hermetic_github_webhook_service(
    webhook_secret: str,
    *,
    signing_key: str = "hermetic-github-webhook-signing-key",
    agent_id: str = DEFAULT_WEBHOOK_AGENT_ID,
) -> GitHubWebhookLifecycleService:
    """In-memory store + freshly issued governance token (unit tests only)."""
    store = OrgMemoryReceiptStore(":memory:")
    coordinator = PRLifecycleEventCoordinator(store, test_mode=True)
    tokens = GovernanceTokenService(signing_key=signing_key)
    identities = IdentityLedger()
    identities.register(agent_id=agent_id, capabilities=[GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY])
    issued = tokens.issue(
        TokenRequest(
            agent_id=agent_id,
            capabilities=[GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY],
            ttl_seconds=3600.0,
        )
    )
    gate = AdmissionGate(tokens, identities)
    return GitHubWebhookLifecycleService(
        webhook_secret=webhook_secret,
        store=store,
        coordinator=coordinator,
        gate=gate,
        governance_token=issued.token_value,
        agent_id=agent_id,
    )
