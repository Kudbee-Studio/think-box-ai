"""Control-plane HTTP API contract (PR #154): versioning and error envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping

CONTROL_PLANE_API_VERSION = "control-plane-api-v1"
SCHEMA_VERSION = "1.0.0"

__all__ = (
    "CONTROL_PLANE_API_VERSION",
    "SCHEMA_VERSION",
    "ControlPlaneApiError",
    "ControlPlaneApiViolation",
    "error_envelope",
    "success_envelope",
    "validate_operation_create_body",
    "validate_required_fields",
)


@dataclass(frozen=True)
class ControlPlaneApiViolation:
    """Single field-level validation failure."""

    code: str
    message: str
    field: str | None = None


@dataclass(frozen=True)
class ControlPlaneApiError:
    """Structured API error (fail-closed)."""

    code: str
    message: str
    http_status: int = 400
    details: tuple[ControlPlaneApiViolation, ...] = ()


def validate_required_fields(
    body: Mapping[str, Any],
    required: tuple[str, ...],
) -> list[ControlPlaneApiViolation]:
    """Return violations for missing or empty required keys."""
    violations: list[ControlPlaneApiViolation] = []
    for key in required:
        if key not in body:
            violations.append(
                ControlPlaneApiViolation(
                    code="missing_field",
                    message=f"missing required field: {key}",
                    field=key,
                )
            )
            continue
        value = body[key]
        if value is None or (isinstance(value, str) and not value.strip()):
            violations.append(
                ControlPlaneApiViolation(
                    code="empty_field",
                    message=f"field must be non-empty: {key}",
                    field=key,
                )
            )
    return violations


def validate_operation_create_body(body: Mapping[str, Any]) -> list[ControlPlaneApiViolation]:
    """Validate POST /operations body."""
    violations = validate_required_fields(body, ("action_type", "operation_id"))
    op_id = body.get("operation_id")
    if isinstance(op_id, str) and len(op_id) > 128:
        violations.append(
            ControlPlaneApiViolation(
                code="operation_id_too_long",
                message="operation_id max length 128",
                field="operation_id",
            )
        )
    return violations


def error_envelope(
    error: ControlPlaneApiError,
    *,
    request_id: str | None = None,
    live_api_called: bool = False,
) -> dict[str, Any]:
    """Standard error JSON envelope."""
    return {
        "ok": False,
        "api_version": CONTROL_PLANE_API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "error": {
            "code": error.code,
            "message": error.message,
            "details": [
                {"code": v.code, "message": v.message, "field": v.field}
                for v in error.details
            ],
        },
        "request_id": request_id,
        "live_api_called": live_api_called,
        "evidence_label": "simulated",
    }


def success_envelope(
    data: Mapping[str, Any],
    *,
    request_id: str | None = None,
    live_api_called: bool = False,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Standard success JSON envelope."""
    payload: MutableMapping[str, Any] = {
        "ok": True,
        "api_version": CONTROL_PLANE_API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "data": dict(data),
        "request_id": request_id,
        "live_api_called": live_api_called,
        "evidence_label": data.get("evidence_label", "simulated"),
    }
    if extra:
        payload.update(extra)
    return dict(payload)
