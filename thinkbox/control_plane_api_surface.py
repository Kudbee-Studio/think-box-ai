"""Compose control-plane API payloads from registry + hermetic clients (PR #154)."""

from __future__ import annotations

from typing import Any

from thinkbox.agent.control_plane.admission import ControlPlaneAdmission
from thinkbox.agent.control_plane.api import chain_health, chain_status
from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.control_plane_receipt_store import get_control_plane_receipt_store
from thinkbox.receipt_chain_query import (
    ChainPage,
    ReceiptChainValidationError,
    fetch_chain_page,
    fetch_head_receipt,
    fetch_tail_receipt,
    validate_receipt_link,
)
from thinkbox.control_plane_api_contract import (
    CONTROL_PLANE_API_VERSION,
    SCHEMA_VERSION,
    success_envelope,
)
from thinkbox.control_plane_hermetic_clients import (
    HermeticGovernanceClient,
    HermeticOrchestrationClient,
)
from thinkbox.control_plane_operation_registry import (
    ControlPlaneOperation,
    OperationRegistry,
    OperationState,
    get_operation_registry,
    new_receipt_id,
)
from thinkbox.control_plane_ops_harden import clamp_query_limit, ops_harden_contract_snippet
from thinkbox.end_link_api import merge_end_link_deepen_fields
from thinkbox.end_link_deepen import (
    run_end_link_batch_validate,
    run_end_link_validate_detailed,
)
from thinkbox.read_cache import weak_etag_from_payload

__all__ = (
    "build_admission_snapshot",
    "build_capacity_snapshot",
    "build_contract_payload",
    "build_operation_list_payload",
    "build_status_snapshot",
    "create_operation_via_admission",
    "build_chain_page_payload",
    "build_chain_head_payload",
    "build_chain_tail_payload",
    "get_chain_payload",
    "build_end_link_batch_payload",
    "build_end_link_validate_payload",
    "validate_chain_receipt_id",
)


def build_contract_payload() -> dict[str, Any]:
    """OpenAPI-adjacent contract metadata (hermetic)."""
    return {
        "api_version": CONTROL_PLANE_API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "routes": [
            "GET /api/v1/control-plane/contract",
            "GET /api/v1/control-plane/status",
            "GET /api/v1/control-plane/admission",
            "GET /api/v1/control-plane/capacity",
            "GET /api/v1/control-plane/operations",
            "POST /api/v1/control-plane/operations",
            "GET /api/v1/control-plane/operations/{operation_id}",
            "POST /api/v1/control-plane/operations/{operation_id}/cancel",
            "GET /api/v1/control-plane/receipts/chain",
            "GET /api/v1/control-plane/receipts/chain/head",
            "GET /api/v1/control-plane/receipts/chain/tail",
            "GET /api/v1/control-plane/receipts/chain/page",
            "GET /api/v1/control-plane/receipts/{receipt_id}/validate",
        ],
        "auth": "Bearer token (THINKBOX_CONTROL_PLANE_TOKEN or local dev)",
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "evidence_label": "simulated",
        **ops_harden_contract_snippet(),
    }


def build_status_snapshot(
    governance: HermeticGovernanceClient,
    orchestration: HermeticOrchestrationClient,
    registry: OperationRegistry | None = None,
) -> dict[str, Any]:
    reg = registry or get_operation_registry()
    return {
        "admission": build_admission_snapshot(governance),
        "capacity": build_capacity_snapshot(orchestration),
        "operations": {"count": reg.count()},
        "kill_switch": {"killed": False, "quarantined": False, "reason": ""},
        "budget": {
            "spent": 0.0,
            "limit": 100.0,
            "currency": "usd",
            "remaining": 100.0,
            "tripped": False,
        },
        "live_api_called": False,
        "evidence_label": "simulated",
        "_hermetic": True,
    }


def build_admission_snapshot(governance: HermeticGovernanceClient) -> dict[str, Any]:
    return {
        "enabled": True,
        "tier": "GOVERNED",
        "checks": governance.checks,
        "denials": governance.denials,
        "token_configured": governance._token is not None,
        "evidence_label": "simulated",
    }


def build_capacity_snapshot(orchestration: HermeticOrchestrationClient) -> dict[str, Any]:
    allocations = orchestration.list_allocations()
    latest_id = next(iter(allocations.keys()), "")
    profile = allocations.get(latest_id, {})
    return {
        "allocated": latest_id,
        "granted": bool(latest_id),
        "allocation_count": len(allocations),
        "resource_profile": profile,
        "evidence_label": "simulated",
    }


async def create_operation_via_admission(
    operation_id: str,
    action_type: str,
    *,
    governance_token: str | None,
    metadata: dict[str, Any] | None = None,
    registry: OperationRegistry | None = None,
) -> tuple[ControlPlaneOperation | None, str]:
    """Admit + register operation; returns (op, error_code)."""
    reg = registry or get_operation_registry()
    existing = reg.get(operation_id)
    if existing is not None:
        return None, "operation_exists"

    gov = HermeticGovernanceClient(governance_token)
    admission = ControlPlaneAdmission(gov)
    decision = await admission.admit(action_type, metadata or {})
    op = reg.create(operation_id, action_type, metadata=metadata)
    if op is None:
        return None, "operation_exists"

    if not decision.allowed:
        reg.transition(
            operation_id,
            OperationState.DENIED,
            reason=decision.reason or "admission_denied",
        )
        return reg.get(operation_id), "admission_denied"
    receipt_id = new_receipt_id()
    etag = weak_etag_from_payload({"operation_id": operation_id, "receipt_id": receipt_id})
    reg.transition(
        operation_id,
        OperationState.ADMITTED,
        receipt_id=receipt_id,
        etag=etag,
    )
    st = get_control_plane_receipt_store()
    agent_id = (metadata or {}).get("agent_id")
    st.append(
        action=action_type,
        status="admitted",
        reason="control_plane_operation",
        evidence_label="simulated",
        metadata={
            "operation_id": operation_id,
            "receipt_id": receipt_id,
            **({"agent_id": agent_id} if agent_id else {}),
        },
    )
    orch = HermeticOrchestrationClient()
    grant = await orch.request_capacity({"cpu_cores": 0.25, "memory_mb": 128})
    if grant.granted:
        reg.transition(operation_id, OperationState.RUNNING)
    return reg.get(operation_id), ""


def build_operation_list_payload(
    registry: OperationRegistry | None = None,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    reg = registry or get_operation_registry()
    lim = clamp_query_limit(limit)
    ops = [op.to_dict() for op in reg.list_operations(limit=lim)]
    return {"operations": ops, "count": len(ops), "live_api_called": False}


def get_chain_payload(
    store: ActionReceiptStore | None = None,
    *,
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    agent_id: str | None = None,
    status_filter: str | None = None,
    evidence_label: str | None = None,
) -> dict[str, Any]:
    st = store or get_control_plane_receipt_store()
    status = chain_status(st)
    health = chain_health(st)
    page = fetch_chain_page(
        st,
        limit=clamp_query_limit(limit),
        cursor=cursor,
        action=action,
        agent_id=agent_id,
        status_filter=status_filter,
        evidence_label=evidence_label,
    )
    body = {
        "chain": status,
        "health": health,
        "page": {
            "receipts": page.receipts,
            "next_cursor": page.next_cursor,
            "total": page.total,
        },
        "live_api_called": False,
    }
    body["etag"] = weak_etag_from_payload(
        {"chain": status, "page": {"total": page.total, "next": page.next_cursor}},
    )
    return body


def build_chain_page_payload(
    *,
    limit: int = 50,
    cursor: str | None = None,
    action: str | None = None,
    agent_id: str | None = None,
    status_filter: str | None = None,
    evidence_label: str | None = None,
    store: ActionReceiptStore | None = None,
) -> dict[str, Any]:
    st = store or get_control_plane_receipt_store()
    page = fetch_chain_page(
        st,
        limit=clamp_query_limit(limit),
        cursor=cursor,
        action=action,
        agent_id=agent_id,
        status_filter=status_filter,
        evidence_label=evidence_label,
    )
    return _page_dict(page)


def build_chain_head_payload(store: ActionReceiptStore | None = None) -> dict[str, Any]:
    st = store or get_control_plane_receipt_store()
    head = fetch_head_receipt(st)
    return {"head": head, "live_api_called": False, "evidence_label": "simulated"}


def build_chain_tail_payload(store: ActionReceiptStore | None = None) -> dict[str, Any]:
    st = store or get_control_plane_receipt_store()
    tail = fetch_tail_receipt(st)
    return {"tail": tail, "live_api_called": False, "evidence_label": "simulated"}


def build_end_link_validate_payload(
    receipt_id: str,
    store: ActionReceiptStore | None = None,
) -> dict[str, Any]:
    """END LINK validate with PR #158 integrity fields (raises on invalid)."""
    st = store or get_control_plane_receipt_store()
    detail = run_end_link_validate_detailed(st, receipt_id)
    if not detail.valid:
        raise ReceiptChainValidationError(
            detail.failure_code or "end_link_invalid",
            detail.failure_message or "END LINK validation failed",
        )
    base = {
        "receipt_id": detail.receipt_id,
        "valid": True,
        "live_api_called": False,
        "evidence_label": detail.evidence_label,
    }
    return merge_end_link_deepen_fields(base, detail.to_dict())


def build_end_link_batch_payload(
    receipt_ids: list[str],
    *,
    limit: int | None = None,
    store: ActionReceiptStore | None = None,
) -> dict[str, Any]:
    """Bulk END LINK validate (per-item fail-closed; HTTP 200 envelope)."""
    st = store or get_control_plane_receipt_store()
    return run_end_link_batch_validate(st, receipt_ids, limit=limit).to_dict()


def validate_chain_receipt_id(receipt_id: str, store: ActionReceiptStore | None = None) -> dict[str, Any]:
    """Backward-compatible validate payload (delegates to deepen builder)."""
    return build_end_link_validate_payload(receipt_id, store=store)


def _page_dict(page: ChainPage) -> dict[str, Any]:
    return {
        "receipts": page.receipts,
        "next_cursor": page.next_cursor,
        "total": page.total,
        "chain_valid": page.chain_valid,
        "live_api_called": False,
        "evidence_label": "simulated",
    }


def wrap_success(data: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return success_envelope(data, request_id=request_id, live_api_called=False)
