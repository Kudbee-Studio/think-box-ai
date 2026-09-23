"""Live-proof operator audit-flip deepen helpers (PR #167 theme A).

Deepens PR #152/#153/#166 operator paths with fail-closed audit-flip predicates.
Hermetic only — no HTTP.
"""

from __future__ import annotations

from typing import Any, Mapping

from thinkbox.kilo_live_proof_operator_prep_deepen import GATE_ID as PREP_DEEPEN_GATE
from thinkbox.kilo_pr166_combined_post165_lane import GATE_ID as PR166_GATE_ID
from thinkbox.live_proof_operator_prep_deepen import (
    founder_credential_readiness,
    operator_prep_checklist_items,
)
from thinkbox.live_smoke_audit_flip_correlation import (
    audit_flip_predicate_report,
    correlation_contract_snippet,
)

__all__ = (
    "OPERATOR_AUDIT_FLIP_DEEPEN_LABEL",
    "OPERATOR_AUDIT_FLIP_DEEPEN_VERSION",
    "audit_flip_deepen_contract_snippet",
    "audit_flip_deepen_markers_present",
    "audit_flip_refused_without_artifacts",
    "operator_audit_flip_checklist_items",
)

OPERATOR_AUDIT_FLIP_DEEPEN_LABEL = "live-proof-operator-audit-flip-deepen"
OPERATOR_AUDIT_FLIP_DEEPEN_VERSION = "1.0.0"

_AUDIT_FLIP_CHECKLIST: tuple[str, ...] = (
    "prep_deepen_gate_closed_hermetic",
    "pr166_combined_lane_closed_hermetic",
    "founder_credential_presence_only_redacted",
    "audit_flip_predicates_evaluated",
    "flip_refused_without_artifact_path",
    "flip_refused_without_live_api_called",
    "flip_refused_without_founder_ack_marker",
    "no_live_http_in_ci",
)


def operator_audit_flip_checklist_items() -> tuple[str, ...]:
    """Stable checklist keys for audit-flip deepen gate."""
    base = operator_prep_checklist_items()
    merged = tuple(base) + _AUDIT_FLIP_CHECKLIST
    return merged


def audit_flip_refused_without_artifacts(
    evidence: Mapping[str, Any] | None = None,
) -> bool:
    """True when audit flip is correctly refused (fail-closed)."""
    doc = evidence if evidence is not None else {}
    report = audit_flip_predicate_report(doc, artifact_exists=False)
    return not report.can_flip


def audit_flip_deepen_markers_present(text: str) -> bool:
    needles = (
        OPERATOR_AUDIT_FLIP_DEEPEN_LABEL,
        PREP_DEEPEN_GATE,
        PR166_GATE_ID,
        "audit_flip_refused_without_artifacts",
    )
    return all(n in text for n in needles)


def audit_flip_deepen_contract_snippet() -> dict[str, Any]:
    readiness = founder_credential_readiness({})
    corr = correlation_contract_snippet()
    refused = audit_flip_refused_without_artifacts({})
    return {
        "label": OPERATOR_AUDIT_FLIP_DEEPEN_LABEL,
        "version": OPERATOR_AUDIT_FLIP_DEEPEN_VERSION,
        "prep_deepen_gate_id": PREP_DEEPEN_GATE,
        "pr166_gate_id": PR166_GATE_ID,
        "checklist_item_count": len(operator_audit_flip_checklist_items()),
        "founder_ready": readiness.ready_for_bounded_live_smoke,
        "audit_flip_refused_default": refused,
        "correlation_label": corr.get("correlation_label"),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
