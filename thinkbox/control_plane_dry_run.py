"""Hermetic Demo-in-10: receipts → admission → webhook → pipeline → founder merge-request.

Exercises merged control-plane modules (#106–#109) in-process without staging,
GitHub merge, or external services. Never claims LIVE_VERIFIED or PRODUCTION_READY.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from thinkbox.admission import AdmissionGate
from thinkbox.github_webhook import (
    DEFAULT_WEBHOOK_AGENT_ID,
    GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY,
    GitHubWebhookLifecycleService,
    compute_github_signature,
)
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    DEFAULT_FOUNDER_AGENT_ID,
    DEFAULT_FOUNDER_PROOF_KEY,
    PIPELINE_FOUNDER_MERGE_CAPABILITY,
    PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
    FounderGatedMergeService,
    PipelineDashboardAggregator,
    compute_founder_merge_proof,
    pipeline_ops_scorecard,
)
from thinkbox.pipeline_waiver import PIPELINE_POLICY_WAIVER_CAPABILITY, PolicyWaiverService
from thinkbox.pipeline_fleet_checkpoint import FleetCheckpointService
from thinkbox.pr_lifecycle_event_hooks import PRLifecycleEventCoordinator

HERMETIC_WEBHOOK_SECRET = "dry-run-webhook-secret-local-only"
HERMETIC_SIGNING_KEY = "dry-run-control-plane-signing-key"
DEFAULT_DRY_RUN_PR = 111
DEFAULT_DRY_RUN_BRANCH = "feat/demo-in-10-control-plane-dry-run"


@dataclass
class ControlPlaneDryRunContext:
    """Shared org-memory + services for webhook and pipeline surfaces."""

    store: OrgMemoryReceiptStore
    coordinator: PRLifecycleEventCoordinator
    webhook_service: GitHubWebhookLifecycleService
    aggregator: PipelineDashboardAggregator
    merge_svc: FounderGatedMergeService
    founder_token: str
    founder_proof_key: str
    webhook_secret: str
    pr_number: int
    bundle: Any = None


@dataclass
class DryRunStep:
    name: str
    ok: bool
    detail: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlPlaneDryRunResult:
    pr_number: int
    steps: list[DryRunStep]
    github_merge_called: bool
    chain_verified: bool
    merge_admitted: bool
    receipt_count: int
    four_state: dict[str, Any]

    def all_steps_ok(self) -> bool:
        return all(s.ok for s in self.steps)


def build_dry_run_four_state(*, ceremony_ok: bool, chain_verified: bool) -> dict[str, Any]:
    """Honest four-state packet for operator dry-runs (LIVE/PROD always blocked)."""
    return {
        "CODE_COMPLETE": True,
        "TEST_VERIFIED": ceremony_ok and chain_verified,
        "LIVE_VERIFIED": False,
        "PRODUCTION_READY": False,
        "live_blocked_reason": "DRY_RUN: no physical staging; PR #110 LIVE drill is separate",
        "production_blocked_reason": "DRY_RUN: founder merge-request only; never GitHub merge",
        "evidence_label": "simulated",
        "auto_merge": False,
        "github_merge_enabled": False,
    }


def _issue_founder_token(
    tokens: GovernanceTokenService,
    agent_id: str,
) -> str:
    from thinkbox.pipeline_dashboard import PipelineQuarantineController

    issued = tokens.issue(
        TokenRequest(
            agent_id=agent_id,
            capabilities=[
                PIPELINE_FOUNDER_MERGE_CAPABILITY,
                PipelineQuarantineController.QUARANTINE_CAPABILITY,
                PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
                PIPELINE_POLICY_WAIVER_CAPABILITY,
            ],
            ttl_seconds=3600.0,
        )
    )
    return issued.token_value


def build_control_plane_dry_run_context(
    *,
    pr_number: int = DEFAULT_DRY_RUN_PR,
    webhook_secret: str = HERMETIC_WEBHOOK_SECRET,
    signing_key: str = HERMETIC_SIGNING_KEY,
    founder_proof_key: str = DEFAULT_FOUNDER_PROOF_KEY,
    founder_agent_id: str = DEFAULT_FOUNDER_AGENT_ID,
    webhook_agent_id: str = DEFAULT_WEBHOOK_AGENT_ID,
) -> ControlPlaneDryRunContext:
    """Wire webhook + pipeline on one in-memory org-memory store."""
    from backend.api.v1.pipeline_dashboard import PipelineDashboardBundle
    from thinkbox.pipeline_dashboard import PipelineQuarantineController

    store = OrgMemoryReceiptStore(":memory:")
    coordinator = PRLifecycleEventCoordinator(store, test_mode=True)

    wh_tokens = GovernanceTokenService(signing_key=f"{signing_key}-webhook")
    wh_identities = IdentityLedger()
    wh_identities.register(agent_id=webhook_agent_id, capabilities=[GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY])
    wh_issued = wh_tokens.issue(
        TokenRequest(
            agent_id=webhook_agent_id,
            capabilities=[GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY],
            ttl_seconds=3600.0,
        )
    )
    wh_gate = AdmissionGate(wh_tokens, wh_identities)
    webhook_service = GitHubWebhookLifecycleService(
        webhook_secret=webhook_secret,
        store=store,
        coordinator=coordinator,
        gate=wh_gate,
        governance_token=wh_issued.token_value,
        agent_id=webhook_agent_id,
    )

    pl_tokens = GovernanceTokenService(signing_key=signing_key)
    pl_identities = IdentityLedger()
    pl_identities.register(
        agent_id=founder_agent_id,
        capabilities=[
            PIPELINE_FOUNDER_MERGE_CAPABILITY,
            PipelineQuarantineController.QUARANTINE_CAPABILITY,
            PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
            PIPELINE_POLICY_WAIVER_CAPABILITY,
        ],
    )
    founder_token = _issue_founder_token(pl_tokens, founder_agent_id)
    pl_gate = AdmissionGate(pl_tokens, pl_identities)
    aggregator = PipelineDashboardAggregator(store)
    merge_svc = FounderGatedMergeService(
        store,
        pl_gate,
        coordinator,
        agent_id=founder_agent_id,
        founder_proof_key=founder_proof_key,
        aggregator=aggregator,
    )
    quarantine = PipelineQuarantineController(store, pl_gate, agent_id=founder_agent_id)
    fleet = FleetCheckpointService(store, aggregator)
    waiver = PolicyWaiverService(store, pl_gate, agent_id=founder_agent_id)
    bundle = PipelineDashboardBundle(
        aggregator=aggregator,
        merge_svc=merge_svc,
        quarantine=quarantine,
        fleet_checkpoint=fleet,
        policy_waiver=waiver,
    )

    return ControlPlaneDryRunContext(
        store=store,
        coordinator=coordinator,
        webhook_service=webhook_service,
        aggregator=aggregator,
        merge_svc=merge_svc,
        founder_token=founder_token,
        founder_proof_key=founder_proof_key,
        webhook_secret=webhook_secret,
        pr_number=pr_number,
        bundle=bundle,
    )


def _signed_payload(secret: str, payload: dict[str, Any]) -> tuple[bytes, str]:
    body = json.dumps(payload).encode("utf-8")
    return body, compute_github_signature(secret, body)


def run_control_plane_dry_run(
    *,
    pr_number: int = DEFAULT_DRY_RUN_PR,
    branch: str = DEFAULT_DRY_RUN_BRANCH,
    exercise_api_handlers: bool = True,
    context: Optional[ControlPlaneDryRunContext] = None,
) -> ControlPlaneDryRunResult:
    """Execute the operator ceremony; optionally invoke FastAPI route handlers in-process."""
    ctx = context or build_control_plane_dry_run_context(pr_number=pr_number)
    ctx.pr_number = pr_number
    steps: list[DryRunStep] = []

    before = ctx.store.count()
    ctx.store.append_lifecycle(
        run_id=f"dry_run_{pr_number}",
        pr_number=pr_number,
        branch=branch,
        from_state="PR_CREATED",
        to_state="IDENTIFY",
        action="dry_run_ceremony_start",
        result="success",
        evidence_label="simulated",
        evidence={"source": "demo_in_10_control_plane_dry_run", "pr_mapping": "PR111"},
    )
    steps.append(
        DryRunStep(
            "org_memory_receipt",
            True,
            f"receipts {before} -> {ctx.store.count()}",
            {"action": "dry_run_ceremony_start"},
        )
    )

    open_payload = {
        "action": "opened",
        "number": pr_number,
        "pull_request": {"head": {"ref": branch, "sha": "dry-run-head-sha"}},
    }
    body, sig = _signed_payload(ctx.webhook_secret, open_payload)
    open_result = ctx.webhook_service.process(body, "pull_request", sig)
    steps.append(
        DryRunStep(
            "webhook_signed_pr_open",
            open_result.http_status == 200 and open_result.admission_allowed,
            open_result.detail,
            {"http_status": open_result.http_status, "admission_allowed": open_result.admission_allowed},
        )
    )

    bad = ctx.webhook_service.process(b"{}", "pull_request", "sha256=invalid")
    steps.append(
        DryRunStep(
            "webhook_bad_signature_fail_closed",
            bad.http_status == 401 and not bad.signature_valid,
            bad.detail,
            {"http_status": bad.http_status},
        )
    )

    ci_payload = {
        "action": "completed",
        "workflow": {"name": "unittest"},
        "workflow_run": {
            "id": 11101,
            "conclusion": "success",
            "pull_requests": [{"number": pr_number}],
        },
    }
    ci_body, ci_sig = _signed_payload(ctx.webhook_secret, ci_payload)
    ci_result = ctx.webhook_service.process(ci_body, "workflow_run", ci_sig)
    steps.append(
        DryRunStep(
            "webhook_signed_ci_success",
            ci_result.http_status == 200,
            ci_result.detail,
            {"outcomes": len(ci_result.outcomes)},
        )
    )

    overview = ctx.aggregator.overview()
    denials = ctx.aggregator.admission_denial_ledger(receipt_limit=200)
    integrity = ctx.aggregator.verify_pr_receipt_integrity(pr_number)
    scorecard = pipeline_ops_scorecard(overview, quarantine=ctx.bundle.quarantine.read())
    steps.append(
        DryRunStep(
            "pipeline_dashboard_rollups",
            overview.get("pr_count", 0) >= 1 and integrity.get("chain_verified"),
            f"pr_count={overview.get('pr_count')} denials={denials.get('total_denials')}",
            {
                "ops_scorecard": scorecard,
                "integrity": integrity,
                "denial_by_reason": denials.get("by_reason"),
            },
        )
    )

    if exercise_api_handlers:
        api_ok, api_detail, api_payload = _run_api_handler_steps(ctx, pr_number, branch)
        steps.append(DryRunStep("pipeline_api_handlers", api_ok, api_detail, api_payload))

    proof = compute_founder_merge_proof(pr_number, ctx.founder_proof_key)
    merge_result = ctx.merge_svc.request_merge(
        pr_number,
        branch=branch,
        governance_token=ctx.founder_token,
        founder_proof=proof,
        metadata={"source": "control_plane_dry_run"},
    )
    steps.append(
        DryRunStep(
            "founder_gated_request_merge",
            merge_result.admitted and not merge_result.github_merge_called,
            merge_result.detail,
            merge_result.to_response_body(),
        )
    )

    direct_merge = ctx.coordinator.request_merge(pr_number)
    steps.append(
        DryRunStep(
            "coordinator_request_merge_never_github",
            not direct_merge.get("merged") and not direct_merge.get("auto_merge"),
            str(direct_merge.get("reason") or "founder_approval_required"),
            {"merged": direct_merge.get("merged"), "auto_merge": direct_merge.get("auto_merge")},
        )
    )

    chain_ok = ctx.store.verify()
    ceremony_ok = all(s.ok for s in steps)
    four_state = build_dry_run_four_state(ceremony_ok=ceremony_ok, chain_verified=chain_ok)

    return ControlPlaneDryRunResult(
        pr_number=pr_number,
        steps=steps,
        github_merge_called=merge_result.github_merge_called,
        chain_verified=chain_ok,
        merge_admitted=merge_result.admitted,
        receipt_count=ctx.store.count(),
        four_state=four_state,
    )


def _run_api_handler_steps(
    ctx: ControlPlaneDryRunContext,
    pr_number: int,
    branch: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Invoke FastAPI route handlers with patched singletons (no external HTTP)."""
    from backend.api.v1.github_webhook import receive_github_webhook, reset_github_webhook_service_cache
    from backend.api.v1.pipeline_dashboard import (
        pipeline_admission_denials,
        pipeline_overview,
        pipeline_pr_integrity,
        pipeline_request_merge,
        reset_pipeline_dashboard_cache,
    )
    from fastapi import Request
    from starlette.responses import JSONResponse

    reset_pipeline_dashboard_cache()
    reset_github_webhook_service_cache()
    proof = compute_founder_merge_proof(pr_number, ctx.founder_proof_key)

    async def _merge_request() -> dict[str, Any]:
        req = MagicMock(spec=Request)
        req.headers = {"content-type": "application/json"}
        req.json = AsyncMock(return_value={"branch": branch})
        return await pipeline_request_merge(
            pr_number,
            req,
            authorization=f"Bearer {ctx.founder_token}",
            x_governance_token=None,
        )

    async def _webhook_request(body: bytes, event: str, signature: str) -> Any:
        req = MagicMock(spec=Request)
        req.body = AsyncMock(return_value=body)
        req.headers = {"X-GitHub-Event": event, "X-Hub-Signature-256": signature}
        return await receive_github_webhook(req)

    with patch(
        "backend.api.v1.pipeline_dashboard._cached_bundle",
        lambda: ctx.bundle,
    ), patch(
        "backend.api.v1.github_webhook._cached_service",
        lambda: ctx.webhook_service,
    ):
        overview_req = MagicMock(spec=Request)
        overview_req.headers = {}
        overview_raw = asyncio.run(pipeline_overview(overview_req))
        overview = (
            json.loads(overview_raw.body.decode("utf-8"))
            if isinstance(overview_raw, JSONResponse)
            else overview_raw
        )
        denials = asyncio.run(pipeline_admission_denials())
        integrity = asyncio.run(pipeline_pr_integrity(pr_number))
        merge_raw = asyncio.run(_merge_request())
        wh_body, wh_sig = _signed_payload(ctx.webhook_secret, {"zen": "dry-run"})
        webhook_resp = asyncio.run(_webhook_request(wh_body, "ping", wh_sig))

    merge_body: dict[str, Any]
    if isinstance(merge_raw, JSONResponse):
        merge_body = json.loads(merge_raw.body.decode("utf-8"))
    else:
        merge_body = merge_raw

    webhook_status = getattr(webhook_resp, "status_code", 200)
    payload = {
        "overview_pr_count": overview.get("pr_count"),
        "denials_total": denials.get("total_denials"),
        "integrity_chain": integrity.get("chain_verified"),
        "merge_body": merge_body,
        "webhook_status": webhook_status,
    }
    ok = (
        overview.get("pr_count", 0) >= 1
        and integrity.get("chain_verified")
        and not merge_body.get("github_merge_called")
        and not merge_body.get("merged")
        and webhook_status == 200
    )
    return ok, "api handlers exercised in-process", payload


def print_dry_run_report(result: ControlPlaneDryRunResult) -> None:
    """Human-readable operator output."""
    print("=== KUDBEE Demo in 10 — Control Plane Dry Run (PR #111 ceremony) ===")
    print(f"PR number (demo): {result.pr_number}")
    print("")
    for idx, step in enumerate(result.steps, start=1):
        mark = "OK" if step.ok else "FAIL"
        print(f"[{idx}/{len(result.steps)}] {step.name}: {mark} — {step.detail}")
    print("")
    print("--- Summary ---")
    print(f"receipt_count: {result.receipt_count}")
    print(f"chain_verified: {result.chain_verified}")
    print(f"merge_admitted: {result.merge_admitted}")
    print(f"github_merge_called: {result.github_merge_called}")
    print("")
    print("--- Four-State Packet ---")
    print(json.dumps(result.four_state, indent=2))
    print("")
    if not result.all_steps_ok():
        print("Ceremony FAILED (fail-closed).")
    else:
        print("Ceremony complete — LIVE_VERIFIED and PRODUCTION_READY remain blocked.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Hermetic control-plane dry-run ceremony")
    parser.add_argument("--pr-number", type=int, default=DEFAULT_DRY_RUN_PR)
    parser.add_argument("--branch", default=DEFAULT_DRY_RUN_BRANCH)
    parser.add_argument(
        "--skip-api-handlers",
        action="store_true",
        help="Skip FastAPI route handler wiring (modules-only path)",
    )
    args = parser.parse_args(argv)
    result = run_control_plane_dry_run(
        pr_number=args.pr_number,
        branch=args.branch,
        exercise_api_handlers=not args.skip_api_handlers,
    )
    print_dry_run_report(result)
    return 0 if result.all_steps_ok() else 1


if __name__ == "__main__":
    sys.exit(main())
