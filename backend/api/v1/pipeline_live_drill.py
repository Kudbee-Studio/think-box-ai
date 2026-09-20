"""Live verification drill API (staging only; never GitHub merge)."""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.api.v1.pipeline_dashboard import (
    _cached_bundle,
    _extract_governance_token,
    _founder_proof_key,
)
from thinkbox.pipeline_dashboard import compute_founder_merge_proof
from thinkbox.pipeline_live_drill import (
    latest_live_attestation,
    preflight_report,
    run_live_drill_if_ready,
)

pipeline_live_drill_router = APIRouter(
    prefix="/api/v1/control-plane/pipeline/live",
    tags=["control-plane", "pipeline", "live-drill"],
)


@pipeline_live_drill_router.get("/preflight")
async def live_drill_preflight() -> dict[str, Any]:
    """Fail-closed prerequisite report (no secrets)."""
    report = preflight_report()
    if not report.get("ready_for_live_drill"):
        return JSONResponse(status_code=503, content=report)
    return report


@pipeline_live_drill_router.get("/attestation/latest")
async def live_attestation_latest() -> dict[str, Any]:
    store = _cached_bundle().aggregator._store  # noqa: SLF001
    row = latest_live_attestation(store)
    if row is None:
        return {"attestation": None, "live_verified": False, "evidence_label": "simulated"}
    att = row.get("attestation") or {}
    return {
        "attestation": att,
        "receipt": row,
        "live_verified": bool(att.get("live_verified")),
        "github_merge_called": bool(att.get("github_merge_called")),
        "merged": bool(att.get("merged")),
    }


@pipeline_live_drill_router.post("/drill/run")
async def live_drill_run(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_governance_token: Optional[str] = Header(None, alias="X-Thinkbox-Governance-Token"),
) -> dict[str, Any]:
    """Run staging live drill when preflight passes; records attestation either way."""
    if os.environ.get("THINKBOX_LIVE_DRILL_ENABLED", "").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=403, detail="THINKBOX_LIVE_DRILL_ENABLED required")

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

    pr_number = int(body.get("pr_number") or 110)
    if pr_number < 1:
        raise HTTPException(status_code=400, detail="invalid pr_number")

    proof_key = _founder_proof_key()
    founder_proof = str(body.get("founder_proof") or body.get("founder_merge_proof") or "")
    if not founder_proof:
        founder_proof = request.headers.get("X-Thinkbox-Founder-Proof") or ""
    if not founder_proof and proof_key:
        founder_proof = compute_founder_merge_proof(pr_number, proof_key)

    bundle = _cached_bundle()
    result = run_live_drill_if_ready(
        merge_svc=bundle.merge_svc,
        aggregator=bundle.aggregator,
        quarantine=bundle.quarantine,
        fleet=bundle.fleet_checkpoint,
        pr_number=pr_number,
        governance_token=token,
        founder_proof=founder_proof.strip(),
        proof_key=proof_key,
    )
    if not result.get("executed"):
        return JSONResponse(status_code=503, content=result)
    return result
