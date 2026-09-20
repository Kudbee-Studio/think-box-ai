"""Pipeline control-plane API: per-PR rollup + founder-gated merge requests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from thinkbox.admission import AdmissionGate
from thinkbox.governance_token import GovernanceTokenService
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    DEFAULT_FOUNDER_AGENT_ID,
    PIPELINE_FOUNDER_MERGE_CAPABILITY,
    PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
    FounderGatedMergeService,
    PipelineDashboardAggregator,
    PipelineDeltaTracker,
    PipelineQuarantineController,
    pipeline_ops_scorecard,
)
from thinkbox.pipeline_audit_packet import build_founder_audit_packet
from thinkbox.pipeline_audit_verify import verify_audit_packet
from thinkbox.pipeline_anomaly import detect_denial_anomalies
from thinkbox.pipeline_correlation import compute_blast_radius
from thinkbox.pipeline_fleet_checkpoint import DEFAULT_FLEET_CHECKPOINT_KEY, FleetCheckpointService, CHECKPOINT_CAPABILITY
from thinkbox.pipeline_readiness import evaluate_merge_readiness
from thinkbox.pipeline_waiver import PIPELINE_POLICY_WAIVER_CAPABILITY, PolicyWaiverService
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
    from thinkbox.pipeline_founder_proof_preflight import resolve_founder_proof_key

    return resolve_founder_proof_key()


@dataclass
class PipelineDashboardBundle:
    aggregator: PipelineDashboardAggregator
    merge_svc: FounderGatedMergeService
    quarantine: PipelineQuarantineController
    fleet_checkpoint: FleetCheckpointService
    policy_waiver: PolicyWaiverService


def build_pipeline_dashboard_bundle(
    *,
    db_path: str | None = None,
    test_mode: bool = True,
) -> PipelineDashboardBundle:
    """Construct aggregator + merge gate + quarantine sharing one store."""
    if not test_mode:
        from thinkbox.pipeline_founder_proof_preflight import assert_founder_proof_key_configured

        assert_founder_proof_key_configured()
    store = OrgMemoryReceiptStore(db_path or _DEFAULT_DB)
    coordinator = PRLifecycleEventCoordinator(store, test_mode=test_mode)
    agent_id = _founder_agent_id()
    tokens = GovernanceTokenService(signing_key=_signing_key())
    identities = IdentityLedger()
    caps = [
        PIPELINE_FOUNDER_MERGE_CAPABILITY,
        PipelineQuarantineController.QUARANTINE_CAPABILITY,
        PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
        PIPELINE_POLICY_WAIVER_CAPABILITY,
    ]
    identities.register(agent_id=agent_id, capabilities=caps)
    gate = AdmissionGate(tokens, identities)
    aggregator = PipelineDashboardAggregator(store)
    merge_svc = FounderGatedMergeService(
        store,
        gate,
        coordinator,
        agent_id=agent_id,
        founder_proof_key=_founder_proof_key(),
        aggregator=aggregator,
    )
    quarantine = PipelineQuarantineController(store, gate, agent_id=agent_id)
    fleet = FleetCheckpointService(store, aggregator)
    waiver = PolicyWaiverService(store, gate, agent_id=agent_id)
    return PipelineDashboardBundle(
        aggregator=aggregator,
        merge_svc=merge_svc,
        quarantine=quarantine,
        fleet_checkpoint=fleet,
        policy_waiver=waiver,
    )


@lru_cache(maxsize=1)
def _cached_bundle() -> PipelineDashboardBundle:
    test_mode = os.getenv("THINKBOX_PIPELINE_TEST_MODE", "true").lower() != "false"
    return build_pipeline_dashboard_bundle(test_mode=test_mode)


_delta_tracker: Optional[PipelineDeltaTracker] = None


def _get_delta_tracker() -> PipelineDeltaTracker:
    global _delta_tracker
    if _delta_tracker is None:
        _delta_tracker = PipelineDeltaTracker(_cached_bundle().aggregator)
    return _delta_tracker


def reset_pipeline_dashboard_cache() -> None:
    """Clear process-local singleton (tests)."""
    global _delta_tracker
    _delta_tracker = None
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
    bundle = _cached_bundle()
    overview = bundle.aggregator.overview()
    q = bundle.quarantine.read()
    overview["quarantine"] = q
    overview["ops_scorecard"] = pipeline_ops_scorecard(overview, quarantine=q)
    return overview


@pipeline_dashboard_router.get("/pr/{pr_number}")
async def pipeline_pr_detail(pr_number: int, receipt_limit: int = 50) -> dict[str, Any]:
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    if receipt_limit < 1 or receipt_limit > 200:
        raise HTTPException(status_code=400, detail="receipt_limit must be 1..200")
    aggregator = _cached_bundle().aggregator
    return aggregator.pr_detail(pr_number, receipt_limit=receipt_limit)


@pipeline_dashboard_router.get("/pr/{pr_number}/integrity")
async def pipeline_pr_integrity(pr_number: int, receipt_limit: int = 500) -> dict[str, Any]:
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    from thinkbox.pipeline_integrity import expanded_pr_integrity

    store = _cached_bundle().aggregator._store  # noqa: SLF001
    return expanded_pr_integrity(store, pr_number, receipt_limit=receipt_limit)


@pipeline_dashboard_router.get("/pr/{pr_number}/merge-readiness")
async def pipeline_merge_readiness(pr_number: int) -> dict[str, Any]:
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    return evaluate_merge_readiness(_cached_bundle().aggregator._store, pr_number).to_dict()  # noqa: SLF001


@pipeline_dashboard_router.get("/pr/{pr_number}/audit-packet")
async def pipeline_audit_packet(pr_number: int, receipt_limit: int = 100) -> dict[str, Any]:
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    key = os.getenv("THINKBOX_PIPELINE_AUDIT_KEY", "hermetic-pipeline-audit-key")
    return build_founder_audit_packet(
        _cached_bundle().aggregator,
        pr_number,
        attestation_key=key,
        receipt_limit=receipt_limit,
    )


@pipeline_dashboard_router.post("/pr/{pr_number}/audit-packet/verify")
async def pipeline_audit_packet_verify(pr_number: int, request: Request) -> dict[str, Any]:
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    body: dict[str, Any] = {}
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            parsed = await request.json()
            if isinstance(parsed, dict):
                body = parsed
    except Exception:
        body = {}
    packet = body.get("packet") if isinstance(body.get("packet"), dict) else body
    if not isinstance(packet, dict) or not packet:
        raise HTTPException(status_code=400, detail="audit_packet_required")
    key = os.getenv("THINKBOX_PIPELINE_AUDIT_KEY", "hermetic-pipeline-audit-key")
    result = verify_audit_packet(packet, attestation_key=key)
    result["pr_number"] = pr_number
    if not result.get("verified"):
        return JSONResponse(status_code=400, content=result)
    return result


@pipeline_dashboard_router.get("/admissions/anomalies")
async def pipeline_admission_anomalies(window: int = 50, spike_ratio: float = 2.5) -> dict[str, Any]:
    if window < 10 or window > 500:
        raise HTTPException(status_code=400, detail="window must be 10..500")
    store = _cached_bundle().aggregator._store  # noqa: SLF001
    return detect_denial_anomalies(store, window=window, spike_ratio=spike_ratio)


@pipeline_dashboard_router.get("/correlation/blast-radius")
async def pipeline_blast_radius(receipt_limit: int = 400) -> dict[str, Any]:
    if receipt_limit < 50 or receipt_limit > 2000:
        raise HTTPException(status_code=400, detail="receipt_limit must be 50..2000")
    return compute_blast_radius(_cached_bundle().aggregator, receipt_limit=receipt_limit)


@pipeline_dashboard_router.get("/checkpoint/latest")
async def pipeline_checkpoint_latest() -> dict[str, Any]:
    latest = _cached_bundle().fleet_checkpoint.latest()
    return latest or {"checkpoint": None, "evidence_label": "simulated"}


@pipeline_dashboard_router.post("/checkpoint/attest")
async def pipeline_checkpoint_attest(
    authorization: Optional[str] = Header(None),
    x_governance_token: Optional[str] = Header(None, alias="X-Thinkbox-Governance-Token"),
) -> dict[str, Any]:
    token = _extract_governance_token(authorization, x_governance_token)
    if not token:
        raise HTTPException(status_code=401, detail="governance_token_required")
    bundle = _cached_bundle()
    decision = bundle.merge_svc._gate.authorize(  # noqa: SLF001
        token,
        _founder_agent_id(),
        PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
        metadata={"action": "fleet_checkpoint"},
    )
    if not decision.allowed:
        return JSONResponse(status_code=403, content={"admitted": False, "detail": decision.reason})
    q = bundle.quarantine.read()
    cp = bundle.fleet_checkpoint.create_checkpoint(quarantine=q)
    return {"admitted": True, "checkpoint": cp.to_dict()}


@pipeline_dashboard_router.get("/checkpoint/verify")
async def pipeline_checkpoint_verify() -> dict[str, Any]:
    return _cached_bundle().fleet_checkpoint.verify_latest()


@pipeline_dashboard_router.get("/poll/deltas")
async def pipeline_poll_deltas() -> dict[str, Any]:
    return _get_delta_tracker().snapshot()


@pipeline_dashboard_router.get("/stream/deltas")
async def pipeline_stream_deltas() -> StreamingResponse:
    """Hermetic SSE: one snapshot event (poll-friendly)."""

    async def _once() -> Any:
        import json

        payload = _get_delta_tracker().snapshot()
        yield f"data: {json.dumps(payload, default=str)}\n\n"

    return StreamingResponse(_once(), media_type="text/event-stream")


@pipeline_dashboard_router.get("/pr/{pr_number}/ci-timeline")
async def pipeline_pr_ci_timeline(pr_number: int, receipt_limit: int = 200) -> dict[str, Any]:
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    events = _cached_bundle().aggregator.ci_status_timeline(pr_number, receipt_limit=receipt_limit)
    return {
        "pr_number": pr_number,
        "events": events,
        "count": len(events),
        "evidence_label": "simulated",
    }


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
    idempotency_key = request.headers.get("X-Thinkbox-Idempotency-Key") or str(body.get("idempotency_key") or "")
    bundle = _cached_bundle()
    result = bundle.merge_svc.request_merge(
        pr_number,
        branch=branch,
        governance_token=token,
        founder_proof=founder_proof.strip(),
        metadata={"source": "control_plane_api"},
        idempotency_key=idempotency_key.strip(),
        quarantine_state=bundle.quarantine.read(),
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
    return _cached_bundle().aggregator.admission_denial_ledger(
        since=since,
        until=until,
        receipt_limit=receipt_limit,
    )


@pipeline_dashboard_router.get("/quarantine")
async def pipeline_quarantine_read() -> dict[str, Any]:
    return _cached_bundle().quarantine.read()


@pipeline_dashboard_router.post("/quarantine")
async def pipeline_quarantine_write(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_governance_token: Optional[str] = Header(None, alias="X-Thinkbox-Governance-Token"),
) -> dict[str, Any]:
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
    result = _cached_bundle().quarantine.set_quarantine(
        quarantined=bool(body.get("quarantined")),
        reason=str(body.get("reason") or "manual"),
        governance_token=token,
    )
    if not result.get("admitted"):
        return JSONResponse(status_code=403, content=result)
    return result


@pipeline_dashboard_router.post("/pr/{pr_number}/policy-waiver")
async def pipeline_policy_waiver(
    pr_number: int,
    request: Request,
    authorization: Optional[str] = Header(None),
    x_governance_token: Optional[str] = Header(None, alias="X-Thinkbox-Governance-Token"),
) -> dict[str, Any]:
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
    reason = str(body.get("reason") or "founder_accepted_risk")
    result = _cached_bundle().policy_waiver.grant_waiver(
        pr_number,
        branch=branch,
        governance_token=token,
        reason=reason,
    )
    result["pr_number"] = pr_number
    result["auto_merge"] = False
    result["github_merge"] = False
    if not result.get("granted"):
        return JSONResponse(status_code=403, content=result)
    return result


@pipeline_dashboard_router.get("/admissions/provenance")
async def pipeline_admission_provenance(
    pr_number: Optional[int] = None,
    limit: int = 200,
) -> dict[str, Any]:
    from thinkbox.pipeline_admission_provenance import collect_admission_provenance, provenance_summary

    store = _cached_bundle().aggregator._store  # noqa: SLF001
    events = collect_admission_provenance(store, pr_number=pr_number, limit=limit)
    return {"events": events, "summary": provenance_summary(events), "auto_merge": False}


@pipeline_dashboard_router.get("/pr/{pr_number}/rollup-consistency")
async def pipeline_rollup_consistency(pr_number: int) -> dict[str, Any]:
    from thinkbox.pipeline_rollup_consistency import verify_pr_rollup_consistency

    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")
    return verify_pr_rollup_consistency(_cached_bundle().aggregator._store, pr_number)  # noqa: SLF001


@pipeline_dashboard_router.get("/reconcile")
async def pipeline_reconcile() -> dict[str, Any]:
    from thinkbox.pipeline_recovery import reconcile_overview_chain

    return reconcile_overview_chain(_cached_bundle().aggregator._store)  # noqa: SLF001


@pipeline_dashboard_router.get("/quarantine/history")
async def pipeline_quarantine_history(limit: int = 100) -> dict[str, Any]:
    from thinkbox.pipeline_quarantine_lifecycle import quarantine_history

    return {
        "history": quarantine_history(_cached_bundle().aggregator._store, limit=limit),  # noqa: SLF001
        "evidence_label": "simulated",
    }


@pipeline_dashboard_router.get("/pr/{pr_number}/ci-timeline/validate")
async def pipeline_ci_timeline_validate(pr_number: int, receipt_limit: int = 200) -> dict[str, Any]:
    from thinkbox.pipeline_ci_timeline import validate_ci_timeline

    events = _cached_bundle().aggregator.ci_status_timeline(pr_number, receipt_limit=receipt_limit)
    return {"pr_number": pr_number, "validation": validate_ci_timeline(events), "events": events}


@pipeline_dashboard_router.get("/health")
async def pipeline_dashboard_health() -> dict[str, Any]:
    bundle = _cached_bundle()
    overview = bundle.aggregator.overview()
    return {
        "capability": PIPELINE_FOUNDER_MERGE_CAPABILITY,
        "founder_agent_id": _founder_agent_id(),
        "pr_count": overview.get("pr_count"),
        "chain_verified": overview.get("chain_verified"),
        "auto_merge": False,
        "github_merge": False,
        "evidence_label": "simulated",
        "live_verified": False,
        "quarantine": bundle.quarantine.read(),
    }
