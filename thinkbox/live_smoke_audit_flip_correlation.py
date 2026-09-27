"""Live-smoke evidence ↔ audit-flip correlation helpers (PR #165 theme A).

Fail-closed predicate reporting so ``live_verified`` cannot be inferred without
founder ack marker, box URL flag, live API flag, and on-disk artifact path.
Hermetic only — no HTTP.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from thinkbox.kilo_live_proof_exec import FOUNDER_ACK_ENV
from thinkbox.kilo_live_smoke_evidence import (
    BOX_URL_PRESENT_FIELD,
    FOUNDER_ACK_MARKER_FIELD,
    can_flip_audit_live_verified,
)
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV

__all__ = (
    "CORRELATION_LABEL",
    "CORRELATION_VERSION",
    "AuditFlipCorrelationReport",
    "audit_flip_predicate_report",
    "correlate_smoke_evidence_with_audit_pass",
    "correlation_contract_snippet",
    "missing_flip_predicates",
    "smoke_operator_evidence_aligns_with_audit",
)

CORRELATION_LABEL = "live-smoke-audit-flip-correlation"
CORRELATION_VERSION = "1.0.0"

_FLIP_PREDICATE_KEYS: tuple[str, ...] = (
    "live_verified_true",
    FOUNDER_ACK_MARKER_FIELD,
    BOX_URL_PRESENT_FIELD,
    "live_api_called_true",
    "artifact_path_present",
    "artifact_exists_on_disk",
)


@dataclass(frozen=True)
class AuditFlipCorrelationReport:
    """Structured predicate evaluation for audit flip correlation."""

    can_flip: bool
    predicates: dict[str, bool]
    missing: tuple[str, ...]
    evidence_id: str | None
    operator_gate_id: str | None


def _artifact_path_from_evidence(evidence: Mapping[str, Any]) -> str:
    path = evidence.get("evidence_artifact_path") or ""
    if isinstance(path, str) and path.strip():
        return path.strip()
    paths = evidence.get("artifact_paths")
    if isinstance(paths, list) and paths:
        first = paths[0]
        if isinstance(first, str):
            return first.strip()
    return ""


def missing_flip_predicates(
    evidence: Mapping[str, Any],
    *,
    artifact_exists: bool = False,
) -> tuple[str, ...]:
    """Return human-readable missing predicate keys (empty when flip allowed)."""
    report = audit_flip_predicate_report(evidence, artifact_exists=artifact_exists)
    return report.missing


def audit_flip_predicate_report(
    evidence: Mapping[str, Any],
    *,
    artifact_exists: bool = False,
) -> AuditFlipCorrelationReport:
    """Evaluate each flip predicate independently (fail-closed)."""
    path = _artifact_path_from_evidence(evidence)
    preds: dict[str, bool] = {
        "live_verified_true": evidence.get("live_verified") is True,
        FOUNDER_ACK_MARKER_FIELD: evidence.get(FOUNDER_ACK_MARKER_FIELD) is True,
        BOX_URL_PRESENT_FIELD: evidence.get(BOX_URL_PRESENT_FIELD) is True,
        "live_api_called_true": evidence.get("live_api_called") is True,
        "artifact_path_present": bool(path),
        "artifact_exists_on_disk": artifact_exists
        or can_flip_audit_live_verified(
            evidence,
            artifact_path=path or None,
            artifact_exists=artifact_exists,
        ),
    }
    missing: list[str] = []
    if evidence.get("live_verified") is not True:
        missing.append("live_verified_not_true")
    if evidence.get(FOUNDER_ACK_MARKER_FIELD) is not True:
        missing.append(FOUNDER_ACK_MARKER_FIELD)
    if evidence.get(BOX_URL_PRESENT_FIELD) is not True:
        missing.append(BOX_URL_PRESENT_FIELD)
    if evidence.get("live_api_called") is not True:
        missing.append("live_api_called")
    if not path:
        missing.append("evidence_artifact_path")
    elif not preds["artifact_exists_on_disk"] and not artifact_exists:
        missing.append("artifact_missing_on_disk")

    can_flip = can_flip_audit_live_verified(
        evidence,
        artifact_path=path or None,
        artifact_exists=artifact_exists,
    )
    return AuditFlipCorrelationReport(
        can_flip=can_flip,
        predicates=preds,
        missing=tuple(missing),
        evidence_id=str(evidence.get("evidence_id") or "") or None,
        operator_gate_id=str(evidence.get("operator_gate_id") or "") or None,
    )


def smoke_operator_evidence_aligns_with_audit(
    evidence: Mapping[str, Any],
    audit_pass: Mapping[str, Any],
) -> bool:
    """True when evidence gate chain references the audit pass pr when present."""
    pr = audit_pass.get("pr_number")
    if pr is None:
        return True
    op_pr = evidence.get("operator_pr_number")
    if op_pr is None:
        return True
    try:
        return int(op_pr) >= int(pr)
    except (TypeError, ValueError):
        return False


def correlate_smoke_evidence_with_audit_pass(
    evidence: Mapping[str, Any],
    audit_pass: Mapping[str, Any],
    *,
    artifact_exists: bool = False,
) -> dict[str, Any]:
    """Produce a redaction-safe correlation blob for operator logs."""
    report = audit_flip_predicate_report(evidence, artifact_exists=artifact_exists)
    return {
        "correlation_label": CORRELATION_LABEL,
        "correlation_version": CORRELATION_VERSION,
        "founder_ack_env_key": FOUNDER_ACK_ENV,
        "box_url_env_key": BOX_URL_ENV,
        "can_flip": report.can_flip,
        "predicates": report.predicates,
        "missing_predicates": list(report.missing),
        "predicate_keys": list(_FLIP_PREDICATE_KEYS),
        "evidence_id": report.evidence_id,
        "operator_gate_id": report.operator_gate_id,
        "audit_pass_pr_number": audit_pass.get("pr_number"),
        "audit_pass_gate_id": audit_pass.get("gate_id"),
        "operator_aligns_with_audit": smoke_operator_evidence_aligns_with_audit(
            evidence,
            audit_pass,
        ),
        "live_verified": False if not report.can_flip else evidence.get("live_verified"),
        "four_state_max": "TEST_VERIFIED",
        "live_api_called": evidence.get("live_api_called") is True,
        "serialized_size": len(json.dumps(report.predicates, sort_keys=True)),
    }


def correlation_contract_snippet() -> dict[str, Any]:
    return {
        "correlation_label": CORRELATION_LABEL,
        "correlation_version": CORRELATION_VERSION,
        "founder_ack_env": FOUNDER_ACK_ENV,
        "box_url_env": BOX_URL_ENV,
        "flip_predicate_count": len(_FLIP_PREDICATE_KEYS),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
