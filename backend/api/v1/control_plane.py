"""Control plane HTTP surface: admission, capacity, operations, receipts (PR #154)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.v1.control_plane_auth import require_control_plane_auth
from backend.api.v1.http_conditional import (
    conditional_json_response,
    conditional_json_response_if_match,
)
from thinkbox.receipt_chain_query import ReceiptChainValidationError
from thinkbox.control_plane_api_contract import (
    ControlPlaneApiError,
    error_envelope,
    validate_operation_create_body,
)
from thinkbox.control_plane_api_surface import (
    build_admission_snapshot,
    build_capacity_snapshot,
    build_contract_payload,
    build_chain_head_payload,
    build_chain_page_payload,
    build_chain_tail_payload,
    build_operation_list_payload,
    build_status_snapshot,
    create_operation_via_admission,
    get_chain_payload,
    validate_chain_receipt_id,
    wrap_success,
)
from thinkbox.control_plane_hermetic_clients import (
    HermeticGovernanceClient,
    HermeticOrchestrationClient,
)
from thinkbox.control_plane_operation_registry import get_operation_registry

control_plane_api = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])

_orchestration = HermeticOrchestrationClient()


def _request_id() -> str:
    return f"cp_req_{uuid.uuid4().hex[:12]}"


@control_plane_api.get("/contract")
async def control_plane_contract(
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Hermetic API contract metadata."""
    return wrap_success(build_contract_payload(), request_id=_request_id())


@control_plane_api.get("/status")
async def control_plane_status(
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Aggregated control-plane status."""
    gov = HermeticGovernanceClient(_token)
    data = build_status_snapshot(gov, _orchestration)
    return wrap_success(data, request_id=_request_id())


@control_plane_api.get("/admission")
async def admission_status(
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Current admission counters."""
    gov = HermeticGovernanceClient(_token)
    return wrap_success(build_admission_snapshot(gov), request_id=_request_id())


@control_plane_api.get("/capacity")
async def capacity_status(
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Hermetic capacity snapshot."""
    return wrap_success(build_capacity_snapshot(_orchestration), request_id=_request_id())


@control_plane_api.get("/operations")
async def list_operations(
    limit: int = 50,
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """List recent control-plane operations."""
    data = build_operation_list_payload()
    if limit != 50:
        ops = data["operations"][: max(1, min(limit, 200))]
        data = {"operations": ops, "count": len(ops), "live_api_called": False}
    return wrap_success(data, request_id=_request_id())


@control_plane_api.post("/operations")
async def create_operation(
    body: dict[str, Any],
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Create operation after governance admission (hermetic)."""
    violations = validate_operation_create_body(body)
    if violations:
        err = ControlPlaneApiError(
            code="validation_failed",
            message="invalid operation body",
            http_status=400,
            details=tuple(violations),
        )
        raise HTTPException(
            status_code=400,
            detail=error_envelope(err, request_id=_request_id()),
        )
    op, err_code = await create_operation_via_admission(
        str(body["operation_id"]),
        str(body["action_type"]),
        governance_token=_token,
        metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
    )
    if err_code == "operation_exists":
        raise HTTPException(status_code=409, detail="operation_exists")
    if op is None:
        raise HTTPException(status_code=500, detail="operation_create_failed")
    payload = wrap_success(op.to_dict(), request_id=_request_id())
    if err_code == "admission_denied":
        raise HTTPException(status_code=403, detail=payload)
    return payload


@control_plane_api.get("/operations/{operation_id}")
async def get_operation(
    operation_id: str,
    request: Request,
    _token: str = Depends(require_control_plane_auth),
):
    """Get one operation; supports If-None-Match when etag present."""
    op = get_operation_registry().get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail="operation_not_found")
    data = op.to_dict()
    envelope = wrap_success(data, request_id=_request_id())
    etag = op.etag
    if etag:
        return conditional_json_response(request, envelope, etag=etag)
    return envelope


@control_plane_api.post("/operations/{operation_id}/cancel")
async def cancel_operation(
    operation_id: str,
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Cancel a non-terminal operation."""
    reg = get_operation_registry()
    op = reg.cancel(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail="operation_not_found")
    return wrap_success(op.to_dict(), request_id=_request_id())


@control_plane_api.get("/receipts/chain")
async def receipts_chain(
    request: Request,
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    agent_id: str | None = None,
    _token: str = Depends(require_control_plane_auth),
):
    """Receipt chain status with conditional GET, pagination, and filters."""
    payload = get_chain_payload(limit=limit, cursor=cursor, action=action, agent_id=agent_id)
    etag = payload.get("etag")
    return conditional_json_response(
        request,
        wrap_success(payload, request_id=_request_id()),
        etag=etag,
    )


@control_plane_api.get("/receipts/chain/page")
async def receipts_chain_page(
    request: Request,
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    agent_id: str | None = None,
    _token: str = Depends(require_control_plane_auth),
):
    """Paginated receipt list only (conditional GET)."""
    page = build_chain_page_payload(
        limit=limit,
        cursor=cursor,
        action=action,
        agent_id=agent_id,
    )
    from thinkbox.control_plane_conditional import chain_read_etag

    etag = chain_read_etag({"page": page})
    return conditional_json_response(
        request,
        wrap_success(page, request_id=_request_id()),
        etag=etag,
    )


@control_plane_api.get("/receipts/chain/head")
async def receipts_chain_head(
    request: Request,
    _token: str = Depends(require_control_plane_auth),
):
    """Genesis-adjacent head receipt read."""
    head = build_chain_head_payload()
    from thinkbox.read_cache import weak_etag_from_payload

    etag = weak_etag_from_payload(head)
    return conditional_json_response(
        request,
        wrap_success(head, request_id=_request_id()),
        etag=etag,
    )


@control_plane_api.get("/receipts/chain/tail")
async def receipts_chain_tail(
    request: Request,
    _token: str = Depends(require_control_plane_auth),
):
    """Latest receipt read."""
    tail = build_chain_tail_payload()
    from thinkbox.read_cache import weak_etag_from_payload

    etag = weak_etag_from_payload(tail)
    return conditional_json_response(
        request,
        wrap_success(tail, request_id=_request_id()),
        etag=etag,
    )


@control_plane_api.get("/receipts/{receipt_id}/validate")
async def receipts_validate_link(
    receipt_id: str,
    request: Request,
    _token: str = Depends(require_control_plane_auth),
):
    """Fail-closed link validation; If-Match required when If-Match header sent."""
    try:
        body = validate_chain_receipt_id(receipt_id)
    except ReceiptChainValidationError as exc:
        raise HTTPException(status_code=404, detail=exc.code) from exc
    from thinkbox.read_cache import weak_etag_from_payload

    etag = weak_etag_from_payload(body)
    return conditional_json_response_if_match(
        request,
        wrap_success(body, request_id=_request_id()),
        etag=etag,
    )
