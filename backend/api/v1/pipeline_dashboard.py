"""Pipeline control-plane API: per-PR rollup + founder-gated merge requests."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from thinkbox.admission import AdmissionGate
from thinkbox.governance_token import GovernanceTokenService
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    DEFAULT_FOUNDER_AGENT_ID,
    DEFAULT_FOUNDER_PROOF_KEY,
    PIPELINE_FOUNDER_MERGE_CAPABILITY,
    FounderGatedMergeService,
    PipelineDashboardAggregator,
)
from thinkbox.pr_lifecycle_event_hooks import PRLifecycleEventCoordinator

pipeline_dashboard_router = APIRouter(
    prefix="/api/v1/control-plane/pipeline",
    tags=["control-plane", "pipeline"],
)

_DEFAULT_DB = os.getenv(
    "THINKBOX_ORG_MEMORY_DB",
    os.path.join("data", "thinkboxmd", "db", "org_memory_receipts.db"),
)


def _founder_agent_id() -> str:
    return os.getenv("THINKBOX_PIPELINE_FOUNDER_AGENT_ID", DEFAULT_FOUNDER_AGENT_ID)


def _signing_key() -> str:
    return os.getenv("THINKBOX_GOVERNANCE_SIGNING_KEY", "pipeline-founder-dev-key")


def _founder_proof_key() -> str:
    return os.getenv("THINKBOX_FOUNDER_MERGE_PROOF_KEY", DEFAULT_FOUNDER_PROOF_KEY)


def build_pipeline_dashboard_bundle(
    *,
    db_path: str | None = None,
    test_mode: bool = True,
) -> tuple[PipelineDashboardAggregator, FounderGatedMergeService]:
    """Construct aggregator + merge gate sharing one store and coordinator."""
    store = OrgMemoryReceiptStore(db_path or _DEFAULT_DB)
    coordinator = PRLifecycleEventCoordinator(store, test_mode=test_mode)
    agent_id = _founder_agent_id()
    tokens = GovernanceTokenService(signing_key=_signing_key())
    identities = IdentityLedger()
    identities.register(agent_id=agent_id, capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY])
    gate = AdmissionGate(tokens, identities)
    aggregator = PipelineDashboardAggregator(store)
    merge_svc = FounderGatedMergeService(
        store,
        gate,
        coordinator,
        agent_id=agent_id,
        founder_proof_key=_founder_proof_key(),
    )
    return aggregator, merge_svc


@lru_cache(maxsize=1)
def _cached_bundle() -> tuple[PipelineDashboardAggregator, FounderGatedMergeService]:
    test_mode = os.getenv("THINKBOX_PIPELINE_TEST_MODE", "true").lower() != "false"
    return build_pipeline_dashboard_bundle(test_mode=test_mode)


def reset_pipeline_dashboard_cache() -> None:
    """Clear process-local singleton (tests)."""
    _cached_bundle.cache_clear()


def _extract_governance_token(
    authorization: Optional[str],
    x_governance_token: Optional[str],
) -> str:
    if x_governance_token:
        return x_governance_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


@pipeline_dashboard_router.get("")
async def pipeline_overview() -> dict[str, Any]:
    """All PR pipeline rows with evidence and admission rollups."""
    aggregator, _ = _cached_bundle()
    return aggregator.overview()


@pipeline_dashboard_router.get("/pr/{pr_number}")
async def pipeline_pr_detail(pr_number: int, receipt_limit: int = 50) -> dict[str, Any]:
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    if receipt_limit < 1 or receipt_limit > 200:
        raise HTTPException(status_code=400, detail="receipt_limit must be 1..200")
    aggregator, _ = _cached_bundle()
    return aggregator.pr_detail(pr_number, receipt_limit=receipt_limit)


@pipeline_dashboard_router.post("/pr/{pr_number}/request-merge")
async def pipeline_request_merge(
    pr_number: int,
    request: Request,
    authorization: Optional[str] = Header(None),
    x_governance_token: Optional[str] = Header(None, alias="X-Thinkbox-Governance-Token"),
) -> dict[str, Any]:
    """Founder-gated merge request — org-memory receipt only; never calls GitHub."""
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    token = _extract_governance_token(authorization, x_governance_token)
    if not token:
        raise HTTPException(status_code=401, detail="governance_token_required")

    body: dict[str, Any] = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            parsed = await request.json()
            if isinstance(parsed, dict):
                body = parsed
    except Exception:
        body = {}

    branch = str(body.get("branch") or "")
    founder_proof = str(body.get("founder_proof") or body.get("founder_merge_proof") or "")
    if not founder_proof:
        founder_proof = request.headers.get("X-Thinkbox-Founder-Proof") or ""
    _, merge_svc = _cached_bundle()
    result = merge_svc.request_merge(
        pr_number,
        branch=branch,
        governance_token=token,
        founder_proof=founder_proof.strip(),
        metadata={"source": "control_plane_api"},
    )
    if result.http_status >= 400 and result.http_status != 403:
        raise HTTPException(status_code=result.http_status, detail=result.detail)
    payload = result.to_response_body()
    payload["pr_number"] = pr_number
    if result.http_status == 403:
        return JSONResponse(status_code=403, content=payload)
    return payload


@pipeline_dashboard_router.get("/admissions/denials")
async def pipeline_admission_denials(
    since: Optional[str] = None,
    until: Optional[str] = None,
    receipt_limit: int = 500,
) -> dict[str, Any]:
    if receipt_limit < 1 or receipt_limit > 2000:
        raise HTTPException(status_code=400, detail="receipt_limit must be 1..2000")
    aggregator, _ = _cached_bundle()
    return aggregator.admission_denial_ledger(
        since=since,
        until=until,
        receipt_limit=receipt_limit,
    )


@pipeline_dashboard_router.get("/health")
async def pipeline_dashboard_health() -> dict[str, Any]:
    aggregator, _ = _cached_bundle()
    overview = aggregator.overview()
    return {
        "capability": PIPELINE_FOUNDER_MERGE_CAPABILITY,
        "founder_agent_id": _founder_agent_id(),
        "pr_count": overview.get("pr_count"),
        "chain_verified": overview.get("chain_verified"),
        "auto_merge": False,
        "github_merge": False,
        "evidence_label": "simulated",
        "live_verified": False,
    }
