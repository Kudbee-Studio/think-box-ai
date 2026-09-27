"""Live-proof operator audit-flip post-#168 helpers (PR #169 theme A).

Deepens PR #152/#153/#168 operator paths with fail-closed audit-flip predicates.
Hermetic only — no HTTP.
"""

from __future__ import annotations

from typing import Any, Mapping

from thinkbox.kilo_live_proof_operator_audit_flip_post167 import GATE_ID as POST167_THEME_A_GATE
from thinkbox.kilo_pr168_combined_post167_lane import GATE_ID as PR168_GATE_ID
from thinkbox.live_proof_operator_audit_flip_post167 import (
    OPERATOR_AUDIT_FLIP_POST167_LABEL,
    audit_flip_refused_post167_without_artifacts,
    operator_audit_flip_post167_checklist_items,
)
from thinkbox.live_proof_operator_prep_deepen import founder_credential_readiness
from thinkbox.live_smoke_audit_flip_correlation import (
    audit_flip_predicate_report,
    correlation_contract_snippet,
)

__all__ = (
    "OPERATOR_AUDIT_FLIP_POST168_LABEL",
    "OPERATOR_AUDIT_FLIP_POST168_VERSION",
    "audit_flip_post168_contract_snippet",
    "audit_flip_post168_markers_present",
    "audit_flip_refused_post168_without_artifacts",
    "operator_audit_flip_post168_checklist_items",
)

OPERATOR_AUDIT_FLIP_POST168_LABEL = "live-proof-operator-audit-flip-post168"
OPERATOR_AUDIT_FLIP_POST168_VERSION = "1.0.0"

_POST168_CHECKLIST: tuple[str, ...] = (
    "audit_flip_post167_gate_closed_hermetic",
    "pr168_combined_lane_closed_hermetic",
    "founder_credential_presence_only_redacted_post168",
    "audit_flip_predicates_evaluated_post168",
    "flip_refused_without_artifact_path_post168",
    "flip_refused_without_live_api_called_post168",
    "flip_refused_without_founder_ack_marker_post168",
    "no_live_http_in_ci_post168",
)


def operator_audit_flip_post168_checklist_items() -> tuple[str, ...]:
    """Stable checklist keys for audit-flip post-#168 gate."""
    base = operator_audit_flip_post167_checklist_items()
    return tuple(base) + _POST168_CHECKLIST


def audit_flip_refused_post168_without_artifacts(
    evidence: Mapping[str, Any] | None = None,
) -> bool:
    """True when audit flip is correctly refused (fail-closed) after #168."""
    doc = evidence if evidence is not None else {}
    report = audit_flip_predicate_report(doc, artifact_exists=False)
    return (
        not report.can_flip
        and audit_flip_refused_post167_without_artifacts(doc)
    )


def audit_flip_post168_markers_present(text: str) -> bool:
    needles = (
        OPERATOR_AUDIT_FLIP_POST168_LABEL,
        POST167_THEME_A_GATE,
        PR168_GATE_ID,
        "audit_flip_refused_post168_without_artifacts",
        OPERATOR_AUDIT_FLIP_POST167_LABEL,
    )
    return all(n in text for n in needles)


def audit_flip_post168_contract_snippet() -> dict[str, Any]:
    readiness = founder_credential_readiness({})
    corr = correlation_contract_snippet()
    refused = audit_flip_refused_post168_without_artifacts({})
    return {
        "label": OPERATOR_AUDIT_FLIP_POST168_LABEL,
        "version": OPERATOR_AUDIT_FLIP_POST168_VERSION,
        "post167_theme_a_gate_id": POST167_THEME_A_GATE,
        "pr168_gate_id": PR168_GATE_ID,
        "checklist_item_count": len(operator_audit_flip_post168_checklist_items()),
        "founder_ready": readiness.ready_for_bounded_live_smoke,
        "audit_flip_refused_default": refused,
        "correlation_label": corr.get("correlation_label"),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
