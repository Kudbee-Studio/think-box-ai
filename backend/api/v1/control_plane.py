"""Control plane HTTP surface: admission, capacity, operations, receipts (PR #154)."""

from __future__ import annotations

import hashlib
import logging
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
    ControlPlaneApiViolation,
    validate_operation_create_body,
)
from thinkbox.control_plane_api_surface import (
    build_admission_snapshot,
    build_capacity_snapshot,
    build_contract_payload,
    build_chain_head_payload,
    build_chain_page_payload,
    build_chain_tail_payload,
    build_end_link_batch_payload,
    build_end_link_validate_payload,
    build_operation_list_payload,
    build_status_snapshot,
    create_operation_via_admission,
    get_chain_payload,
    wrap_success,
)
from thinkbox.end_link_deepen import evaluate_end_link_batch_body
from thinkbox.end_link_api_ops_harden import (
    OpsRouteTiming,
    enrich_batch_validate_payload,
    enrich_validate_payload,
    lookup_batch_idempotency_replay,
    normalize_failure_code,
    parse_batch_idempotency_key,
    register_batch_idempotency_replay,
    validate_chain_filter_query,
)
from thinkbox.control_plane_hermetic_clients import (
    HermeticGovernanceClient,
    HermeticOrchestrationClient,
)
from thinkbox.control_plane_operation_registry import get_operation_registry
from thinkbox.control_plane_ops_harden import (
    IdempotencyConflict,
    OpsRateLimitExceeded,
    clamp_query_limit,
    get_idempotency_registry,
    get_ops_rate_limiter,
    http_exception_detail,
    redact_mapping_for_logs,
)

control_plane_api = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])

_orchestration = HermeticOrchestrationClient()
_logger = logging.getLogger(__name__)


def _request_id() -> str:
    return f"cp_req_{uuid.uuid4().hex[:12]}"


def _client_rate_key(token: str, request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"{host}:{digest}"


def _enforce_ops_rate_limit(request: Request, token: str) -> None:
    try:
        get_ops_rate_limiter().check(_client_rate_key(token, request))
    except OpsRateLimitExceeded as exc:
        err = ControlPlaneApiError(
            code="rate_limit_exceeded",
            message="control-plane ops rate limit exceeded",
            http_status=429,
            details=(
                ControlPlaneApiViolation(
                    code="retry_after_seconds",
                    message=str(int(exc.retry_after_seconds)),
                    field="Retry-After",
                ),
            ),
        )
        raise HTTPException(
            status_code=429,
            detail=http_exception_detail(err, request_id=_request_id()),
            headers={"Retry-After": str(int(exc.retry_after_seconds))},
        ) from exc


def _chain_filter_error(filter_errors: list[str]) -> HTTPException:
    code = normalize_failure_code(filter_errors[0]) if filter_errors else "chain_filter_invalid"
    return _api_error(
        code or "chain_filter_invalid",
        "receipt chain filter query invalid",
        http_status=400,
        details=tuple(
            ControlPlaneApiViolation(code=err, message=err, field="query")
            for err in filter_errors[:5]
        ),
    )


def _api_error(
    code: str,
    message: str,
    *,
    http_status: int,
    details: tuple[ControlPlaneApiViolation, ...] = (),
) -> HTTPException:
    err = ControlPlaneApiError(
        code=code,
        message=message,
        http_status=http_status,
        details=details,
    )
    return HTTPException(
        status_code=http_status,
        detail=http_exception_detail(err, request_id=_request_id()),
    )


@control_plane_api.get("/contract")
async def control_plane_contract(
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Hermetic API contract metadata."""
    return wrap_success(build_contract_payload(), request_id=_request_id())


@control_plane_api.get("/status")
async def control_plane_status(
    request: Request,
    token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Aggregated control-plane status."""
    _enforce_ops_rate_limit(request, token)
    gov = HermeticGovernanceClient(token)
    data = build_status_snapshot(gov, _orchestration)
    return wrap_success(data, request_id=_request_id())


@control_plane_api.get("/admission")
async def admission_status(
    request: Request,
    token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Current admission counters."""
    _enforce_ops_rate_limit(request, token)
    gov = HermeticGovernanceClient(token)
    return wrap_success(build_admission_snapshot(gov), request_id=_request_id())


@control_plane_api.get("/capacity")
async def capacity_status(
    request: Request,
    token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Hermetic capacity snapshot."""
    _enforce_ops_rate_limit(request, token)
    return wrap_success(build_capacity_snapshot(_orchestration), request_id=_request_id())


@control_plane_api.get("/operations")
async def list_operations(
    limit: int = 50,
    _token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """List recent control-plane operations."""
    lim = clamp_query_limit(limit)
    data = build_operation_list_payload(limit=lim)
    return wrap_success(data, request_id=_request_id())


@control_plane_api.post("/operations")
async def create_operation(
    body: dict[str, Any],
    request: Request,
    token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Create operation after governance admission (hermetic)."""
    _enforce_ops_rate_limit(request, token)
    violations = validate_operation_create_body(body)
    if violations:
        raise _api_error(
            "validation_failed",
            "invalid operation body",
            http_status=400,
            details=tuple(violations),
        )

    idem_key = (request.headers.get("Idempotency-Key") or "").strip()
    operation_id = str(body["operation_id"])
    if idem_key:
        registry = get_idempotency_registry()
        existing_op_id = registry.lookup(idem_key)
        if existing_op_id:
            op = get_operation_registry().get(existing_op_id)
            if op is not None:
                return wrap_success(op.to_dict(), request_id=_request_id())
        try:
            registry.register(idem_key, operation_id=operation_id, body=body)
        except IdempotencyConflict:
            raise _api_error(
                "idempotency_conflict",
                "Idempotency-Key reused with different body",
                http_status=409,
            ) from None

    _logger.debug(
        "control_plane create_operation %s",
        redact_mapping_for_logs({"operation_id": operation_id, "body": body}),
    )

    op, err_code = await create_operation_via_admission(
        operation_id,
        str(body["action_type"]),
        governance_token=token,
        metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
    )
    if err_code == "operation_exists":
        if idem_key:
            replay = get_operation_registry().get(operation_id)
            if replay is not None:
                return wrap_success(replay.to_dict(), request_id=_request_id())
        raise _api_error("operation_exists", "operation_id already registered", http_status=409)
    if op is None:
        raise _api_error("operation_create_failed", "operation create failed", http_status=500)
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
        raise _api_error("operation_not_found", "unknown operation_id", http_status=404)
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
        raise _api_error("operation_not_found", "unknown operation_id", http_status=404)
    return wrap_success(op.to_dict(), request_id=_request_id())


@control_plane_api.get("/receipts/chain")
async def receipts_chain(
    request: Request,
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    agent_id: str | None = None,
    status: str | None = None,
    evidence_label: str | None = None,
    token: str = Depends(require_control_plane_auth),
):
    """Receipt chain status with conditional GET, pagination, and filters."""
    _enforce_ops_rate_limit(request, token)
    filters, filter_errors = validate_chain_filter_query(
        status=status,
        evidence_label=evidence_label,
        action=action,
        agent_id=agent_id,
    )
    if filter_errors:
        raise _chain_filter_error(filter_errors)
    lim = clamp_query_limit(limit)
    payload = get_chain_payload(
        limit=lim,
        cursor=cursor,
        action=filters.action,
        agent_id=filters.agent_id,
        status_filter=filters.status_filter,
        evidence_label=filters.evidence_label,
    )
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
    status: str | None = None,
    evidence_label: str | None = None,
    token: str = Depends(require_control_plane_auth),
):
    """Paginated receipt list only (conditional GET)."""
    _enforce_ops_rate_limit(request, token)
    filters, filter_errors = validate_chain_filter_query(
        status=status,
        evidence_label=evidence_label,
        action=action,
        agent_id=agent_id,
    )
    if filter_errors:
        raise _chain_filter_error(filter_errors)
    lim = clamp_query_limit(limit)
    page = build_chain_page_payload(
        limit=lim,
        cursor=cursor,
        action=filters.action,
        agent_id=filters.agent_id,
        status_filter=filters.status_filter,
        evidence_label=filters.evidence_label,
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
    token: str = Depends(require_control_plane_auth),
):
    """Genesis-adjacent head receipt read."""
    _enforce_ops_rate_limit(request, token)
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
    token: str = Depends(require_control_plane_auth),
):
    """Latest receipt read."""
    _enforce_ops_rate_limit(request, token)
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
    token: str = Depends(require_control_plane_auth),
):
    """Fail-closed link validation; If-Match required when If-Match header sent."""
    _enforce_ops_rate_limit(request, token)
    timing = OpsRouteTiming.start("GET /receipts/{receipt_id}/validate")
    try:
        body = build_end_link_validate_payload(receipt_id)
    except ReceiptChainValidationError as exc:
        raise _api_error(
            normalize_failure_code(exc.code) or exc.code,
            exc.message,
            http_status=404,
        ) from exc
    body = enrich_validate_payload(body, timing=timing)
    from thinkbox.read_cache import weak_etag_from_payload

    etag = weak_etag_from_payload(body)
    return conditional_json_response_if_match(
        request,
        wrap_success(body, request_id=_request_id()),
        etag=etag,
    )


@control_plane_api.post("/receipts/validate/batch")
async def receipts_validate_batch(
    request: Request,
    token: str = Depends(require_control_plane_auth),
) -> dict[str, Any]:
    """Bulk END LINK validate (PR #158); per-receipt fail-closed inside envelope."""
    _enforce_ops_rate_limit(request, token)
    timing = OpsRouteTiming.start("POST /receipts/validate/batch")
    try:
        body = await request.json()
    except Exception as exc:
        raise _api_error("invalid_json", "request body must be JSON", http_status=400) from exc
    if not isinstance(body, dict):
        raise _api_error("invalid_body", "body must be an object", http_status=400)
    idem_key = parse_batch_idempotency_key(request.headers.get("Idempotency-Key"))
    if idem_key:
        try:
            cached = lookup_batch_idempotency_replay(idem_key, body)
        except IdempotencyConflict:
            raise _api_error(
                "idempotency_conflict",
                "Idempotency-Key reused with different batch body",
                http_status=409,
            ) from None
        if cached is not None:
            return wrap_success(cached, request_id=_request_id())
    receipt_ids, parse_errors = evaluate_end_link_batch_body(body)
    if parse_errors:
        raise _api_error(
            normalize_failure_code(parse_errors[0]) or parse_errors[0],
            "batch validate body invalid",
            http_status=400,
        )
    limit = body.get("limit")
    lim = clamp_query_limit(limit) if limit is not None else None
    payload = build_end_link_batch_payload(receipt_ids, limit=lim)
    payload = enrich_batch_validate_payload(payload, timing=timing, idempotency_key=idem_key)
    if idem_key:
        try:
            register_batch_idempotency_replay(idem_key, body, payload)
        except IdempotencyConflict:
            raise _api_error(
                "idempotency_conflict",
                "Idempotency-Key reused with different batch body",
                http_status=409,
            ) from None
    _logger.debug("end_link_batch_validate %s", redact_mapping_for_logs(payload))
    return wrap_success(payload, request_id=_request_id())
