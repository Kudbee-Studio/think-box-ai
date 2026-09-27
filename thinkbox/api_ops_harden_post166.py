"""API / ops harden post-#166 helpers (PR #167 theme B).

Fail-closed response envelopes layered on PR #166 combined post-#165 lane.
Hermetic only — no HTTP.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from thinkbox.api_ops_harden_post165 import (
    API_OPS_POST165_LABEL,
    build_post165_fail_closed_envelope,
    validate_post165_ops_envelope,
)
from thinkbox.control_plane_post164_deepen import (
    POST164_DEEPEN_LABEL,
    assert_hermetic_control_plane_response,
)
from thinkbox.kilo_api_ops_harden_post165 import GATE_ID as POST165_OPS_GATE
from thinkbox.kilo_pr166_combined_post165_lane import GATE_ID as PR166_GATE_ID

__all__ = (
    "API_OPS_POST166_LABEL",
    "API_OPS_POST166_VERSION",
    "api_ops_post166_contract_snippet",
    "api_ops_post166_markers_present",
    "build_post166_fail_closed_envelope",
    "validate_post166_ops_envelope",
)

API_OPS_POST166_LABEL = "api-ops-harden-post166"
API_OPS_POST166_VERSION = "1.0.0"

_GATE_TOKEN_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")


def validate_post166_ops_envelope(
    body: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Validate ops envelope after PR #166 gates (errors + normalized body)."""
    payload, errors = validate_post165_ops_envelope(body)
    gate_id = payload.get("post166_prior_gate_id")
    if gate_id is not None:
        if not isinstance(gate_id, str) or not _GATE_TOKEN_RE.match(gate_id):
            errors.append("post166_prior_gate_id_invalid")
        elif gate_id != PR166_GATE_ID:
            errors.append("post166_prior_gate_id_not_pr166")
    payload.setdefault("live_verified", False)
    payload.setdefault("live_api_called", False)
    if payload.get("live_verified") is True:
        errors.append("live_verified_forbidden_in_hermetic_request")
    if payload.get("live_api_called") is True:
        errors.append("live_api_forbidden")
    return payload, errors


def build_post166_fail_closed_envelope(
    *,
    gate_id: str,
    detail: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Build a hermetic fail-closed ops envelope for post-#166 consumers."""
    base = build_post165_fail_closed_envelope(
        gate_id=gate_id,
        detail=detail,
        correlation_id=correlation_id,
    )
    body: dict[str, Any] = dict(base)
    body["post166_label"] = API_OPS_POST166_LABEL
    body["post166_prior_gate_id"] = PR166_GATE_ID
    body["post165_ops_gate_id"] = POST165_OPS_GATE
    normalized, errors = validate_post166_ops_envelope(body)
    assert not errors, f"internal envelope invalid: {errors}"
    response_violations = assert_hermetic_control_plane_response(normalized)
    assert not response_violations, f"response violations: {response_violations}"
    normalized.setdefault("four_state_max", "TEST_VERIFIED")
    return normalized


def api_ops_post166_markers_present(text: str) -> bool:
    needles = (
        API_OPS_POST166_LABEL,
        PR166_GATE_ID,
        POST165_OPS_GATE,
        "fail_closed",
        POST164_DEEPEN_LABEL,
        API_OPS_POST165_LABEL,
    )
    return all(n in text for n in needles)


def api_ops_post166_contract_snippet() -> dict[str, Any]:
    return {
        "label": API_OPS_POST166_LABEL,
        "version": API_OPS_POST166_VERSION,
        "pr166_gate_id": PR166_GATE_ID,
        "post165_ops_gate_id": POST165_OPS_GATE,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
