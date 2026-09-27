"""Control-plane post-#164 deepen helpers (PR #165 theme B).

Smallest fail-closed surface extension after governance-evidence Live-proof readiness.
Hermetic only — no HTTP. Default claims: live_verified: false, live_api_called: false.

Markers for gate checks: api-ops-harden, governance_evidence_live_proof_readiness,
governance-evidence-live-proof-readiness (PR #164 layer).
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from thinkbox.control_plane_ops_harden import (
    OPS_HARDEN_LABEL,
    clamp_query_limit,
    redact_mapping_for_logs,
)
from thinkbox.governance_evidence_live_proof_readiness import (
    GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_LABEL,
)
from thinkbox.kilo_governance_evidence_live_proof_readiness import GATE_ID as PR164_GATE_ID

__all__ = (
    "POST164_DEEPEN_LABEL",
    "POST164_DEEPEN_VERSION",
    "assert_hermetic_control_plane_response",
    "control_plane_post164_contract_snippet",
    "normalize_control_plane_correlation_id",
    "post164_deepen_markers_present",
    "validate_post164_request_envelope",
)

POST164_DEEPEN_LABEL = "control-plane-post164-deepen"
POST164_DEEPEN_VERSION = "1.0.0"

_CORRELATION_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


def normalize_control_plane_correlation_id(value: str | None) -> str | None:
    """Return a safe correlation id or None when invalid."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed or len(trimmed) > 128:
        return None
    if not _CORRELATION_ID_RE.match(trimmed):
        return None
    return trimmed


def validate_post164_request_envelope(
    body: Mapping[str, Any] | None,
    *,
    limit: int | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Validate a minimal control-plane deepen request (errors list, redacted body)."""
    errors: list[str] = []
    payload: dict[str, Any] = dict(body or {})
    if payload.get("live_verified") is True:
        errors.append("live_verified_forbidden_in_hermetic_request")
    if payload.get("live_api_called") is True:
        errors.append("live_api_called_forbidden_in_hermetic_request")
    corr = normalize_control_plane_correlation_id(
        str(payload.get("correlation_id") or "") or None
    )
    if payload.get("correlation_id") and corr is None:
        errors.append("correlation_id_invalid")
    safe_limit = clamp_query_limit(limit)
    redacted = redact_mapping_for_logs(payload)
    out = {
        "correlation_id": corr,
        "limit": safe_limit,
        "four_state_max": "TEST_VERIFIED",
        "live_verified": False,
        "live_api_called": False,
        "governance_readiness_gate_id": PR164_GATE_ID,
        "redacted_body": redacted,
    }
    return out, errors


def assert_hermetic_control_plane_response(response: Mapping[str, Any]) -> list[str]:
    """Fail-closed checks on API response shapes (hermetic tests)."""
    violations: list[str] = []
    if response.get("live_verified") is True:
        violations.append("response_live_verified_true")
    if response.get("production_ready") is True:
        violations.append("response_production_ready_true")
    fs = response.get("four_state_max")
    if fs in ("LIVE_VERIFIED", "PRODUCTION_READY"):
        violations.append("response_four_state_cap_exceeded")
    return violations


def post164_deepen_markers_present(blob: str) -> bool:
    required = (
        POST164_DEEPEN_LABEL,
        OPS_HARDEN_LABEL,
        GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_LABEL,
        PR164_GATE_ID,
        "live_verified: false",
    )
    return all(marker in blob for marker in required)


def control_plane_post164_contract_snippet() -> dict[str, Any]:
    return {
        "post164_deepen": POST164_DEEPEN_LABEL,
        "post164_deepen_version": POST164_DEEPEN_VERSION,
        "ops_harden": OPS_HARDEN_LABEL,
        "governance_evidence_live_proof_readiness": GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_LABEL,
        "pr164_gate_id": PR164_GATE_ID,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
