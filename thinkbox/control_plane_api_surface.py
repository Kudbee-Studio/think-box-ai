"""Compose control-plane API payloads from registry + hermetic clients (PR #154)."""

from __future__ import annotations

from typing import Any

from thinkbox.agent.control_plane.admission import ControlPlaneAdmission
from thinkbox.agent.control_plane.api import chain_health, chain_status
from thinkbox.agent.control_plane.store import ActionReceiptStore
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
from thinkbox.read_cache import weak_etag_from_payload

__all__ = (
    "build_admission_snapshot",
    "build_capacity_snapshot",
    "build_contract_payload",
    "build_operation_list_payload",
    "build_status_snapshot",
    "create_operation_via_admission",
    "get_chain_payload",
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
        ],
        "auth": "Bearer token (THINKBOX_CONTROL_PLANE_TOKEN or local dev)",
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "evidence_label": "simulated",
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
    orch = HermeticOrchestrationClient()
    grant = await orch.request_capacity({"cpu_cores": 0.25, "memory_mb": 128})
    if grant.granted:
        reg.transition(operation_id, OperationState.RUNNING)
    return reg.get(operation_id), ""


def build_operation_list_payload(registry: OperationRegistry | None = None) -> dict[str, Any]:
    reg = registry or get_operation_registry()
    ops = [op.to_dict() for op in reg.list_operations()]
    return {"operations": ops, "count": len(ops), "live_api_called": False}


def get_chain_payload(store: ActionReceiptStore | None = None) -> dict[str, Any]:
    st = store or ActionReceiptStore()
    status = chain_status(st)
    health = chain_health(st)
    body = {"chain": status, "health": health, "live_api_called": False}
    body["etag"] = weak_etag_from_payload(status)
    return body


def wrap_success(data: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return success_envelope(data, request_id=request_id, live_api_called=False)
