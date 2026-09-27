"""Pure assertion helpers for control-plane hermetic e2e (PR #162).

No HTTP — used by e2e tests and the KILO gate fixture runner.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = (
    "CONTROL_PLANE_E2E_DEEPEN_LABEL",
    "CONTROL_PLANE_E2E_DEEPEN_VERSION",
    "assert_batch_item_shape",
    "assert_fail_closed_envelope",
    "assert_ops_timing_honesty",
    "assert_success_envelope_honesty",
    "assert_validate_integrity_fields",
    "control_plane_e2e_contract_snippet",
)

CONTROL_PLANE_E2E_DEEPEN_LABEL = "control-plane-e2e-deepen"
CONTROL_PLANE_E2E_DEEPEN_VERSION = "1.0.0"


def assert_success_envelope_honesty(body: Mapping[str, Any]) -> list[str]:
    """Top-level success envelope must not claim live verification."""
    errors: list[str] = []
    if not body.get("ok", False):
        errors.append("envelope_not_ok")
    if body.get("live_api_called", True):
        errors.append("live_api_called_true")
    if body.get("live_verified", False):
        errors.append("live_verified_true")
    data = body.get("data")
    if isinstance(data, dict) and data.get("live_api_called", False):
        errors.append("data_live_api_called")
    return errors


def assert_fail_closed_envelope(body: Mapping[str, Any]) -> list[str]:
    """Error detail envelopes remain fail-closed (no live claims)."""
    errors: list[str] = []
    detail = body.get("detail")
    if isinstance(detail, dict):
        if detail.get("ok", True) is not False and detail.get("ok") is not None:
            if "error" not in detail and "code" not in detail.get("error", {}):
                pass
        if detail.get("live_verified", False):
            errors.append("detail_live_verified")
        if detail.get("live_api_called", False):
            errors.append("detail_live_api_called")
    return errors


def assert_ops_timing_honesty(data: Mapping[str, Any]) -> list[str]:
    ops = data.get("ops")
    if not isinstance(ops, dict):
        return ["ops_missing"]
    errors: list[str] = []
    if ops.get("live_verified", False):
        errors.append("ops_live_verified")
    if ops.get("four_state_max") != "TEST_VERIFIED":
        errors.append("ops_four_state")
    timing = ops.get("timing_ms")
    if timing is None or int(timing) < 0:
        errors.append("ops_timing_ms")
    if not ops.get("idempotent_retry_safe", False) and "validate" in str(ops.get("route", "")):
        errors.append("ops_idempotent_validate")
    return errors


def assert_validate_integrity_fields(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("receipt_id", "valid", "link_integrity", "evidence_label"):
        if key not in data:
            errors.append(f"missing_{key}")
    if data.get("evidence_label") not in ("simulated", "verified", "inferred", "physically_measured"):
        errors.append("evidence_label")
    if data.get("valid") and data.get("link_integrity") not in ("ok", "unknown"):
        errors.append("link_integrity_valid_mismatch")
    return errors


def assert_batch_item_shape(item: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if "receipt_id" not in item:
        errors.append("item_receipt_id")
    if "valid" not in item:
        errors.append("item_valid")
    if item.get("failure_code") and item.get("valid"):
        errors.append("item_failure_when_valid")
    return errors


def control_plane_e2e_contract_snippet() -> dict[str, Any]:
    return {
        "control_plane_e2e_deepen": CONTROL_PLANE_E2E_DEEPEN_LABEL,
        "control_plane_e2e_deepen_version": CONTROL_PLANE_E2E_DEEPEN_VERSION,
        "live_api_called": False,
        "live_verified": False,
        "four_state_max": "TEST_VERIFIED",
    }
