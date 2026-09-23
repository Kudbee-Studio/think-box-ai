"""API / ops harden post-#165 helpers (PR #166 theme B).

Fail-closed response envelopes layered on PR #165 combined harden umbrella.
Hermetic only — no HTTP.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from thinkbox.control_plane_post164_deepen import (
    POST164_DEEPEN_LABEL,
    assert_hermetic_control_plane_response,
    validate_post164_request_envelope,
)
from thinkbox.kilo_pr165_combined_harden_era_chronicle import GATE_ID as PR165_GATE_ID

__all__ = (
    "API_OPS_POST165_LABEL",
    "API_OPS_POST165_VERSION",
    "api_ops_post165_contract_snippet",
    "api_ops_post165_markers_present",
    "build_post165_fail_closed_envelope",
    "validate_post165_ops_envelope",
)

API_OPS_POST165_LABEL = "api-ops-harden-post165"
API_OPS_POST165_VERSION = "1.0.0"

_GATE_TOKEN_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")


def validate_post165_ops_envelope(
    body: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Validate ops envelope after PR #165 gates (errors + normalized body)."""
    payload, errors = validate_post164_request_envelope(body)
    gate_id = payload.get("prior_gate_id")
    if gate_id is not None:
        if not isinstance(gate_id, str) or not _GATE_TOKEN_RE.match(gate_id):
            errors.append("prior_gate_id_invalid")
        elif gate_id != PR165_GATE_ID:
            errors.append("prior_gate_id_not_pr165")
    payload.setdefault("live_verified", False)
    payload.setdefault("live_api_called", False)
    if payload.get("live_verified") is True:
        errors.append("live_verified_forbidden")
    if payload.get("live_api_called") is True:
        errors.append("live_api_forbidden")
    return payload, errors


def build_post165_fail_closed_envelope(
    *,
    gate_id: str,
    detail: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Build a hermetic fail-closed ops envelope for control-plane consumers."""
    body: dict[str, Any] = {
        "gate_id": gate_id,
        "detail": detail,
        "prior_gate_id": PR165_GATE_ID,
        "post164_label": POST164_DEEPEN_LABEL,
        "post165_label": API_OPS_POST165_LABEL,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
    if correlation_id:
        body["correlation_id"] = correlation_id
    normalized, errors = validate_post165_ops_envelope(body)
    assert not errors, f"internal envelope invalid: {errors}"
    return assert_hermetic_control_plane_response(normalized)


def api_ops_post165_markers_present(text: str) -> bool:
    needles = (API_OPS_POST165_LABEL, PR165_GATE_ID, "fail_closed", POST164_DEEPEN_LABEL)
    return all(n in text for n in needles)


def api_ops_post165_contract_snippet() -> dict[str, Any]:
    return {
        "label": API_OPS_POST165_LABEL,
        "version": API_OPS_POST165_VERSION,
        "pr165_gate_id": PR165_GATE_ID,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
