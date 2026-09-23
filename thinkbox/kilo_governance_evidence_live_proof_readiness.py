"""Hermetic governance-evidence Live-proof readiness gate (PR #164).

Layers on PR #162 ``control-plane-e2e-deepen`` and PR #145 ``governance-evidence``.
Proves the governance-evidence path is ready for a future Live proof without live HTTP.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.governance_evidence_live_proof_readiness import (
    GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_LABEL,
    GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_VERSION,
    evaluate_governance_evidence_hermetic_unit,
    governance_evidence_live_proof_readiness_contract_snippet,
    live_proof_prereqs_satisfied,
    minimal_valid_readiness_document,
    validate_readiness_document,
)
from thinkbox.kilo_control_plane_e2e_deepen import (
    GATE_ID as PRIOR_E2E_GATE_ID,
    hermetic_control_plane_e2e_deepen_check,
    minimal_control_plane_e2e_deepen_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence import (
    GATE_ID as GOVERNANCE_EVIDENCE_GATE_ID,
    governance_evidence_gate_closed,
    hermetic_governance_operator_check,
)
from thinkbox.kilo_live_proof_exec import FOUNDER_ACK_ENV
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "PRIOR_GATE_IDS",
    "VERIFY_SCRIPT_REL",
    "GovernanceEvidenceLiveProofReadinessEvidence",
    "GovernanceEvidenceLiveProofReadinessResult",
    "GovernanceEvidenceLiveProofReadinessViolation",
    "evaluate_governance_evidence_live_proof_readiness",
    "governance_evidence_live_proof_readiness_contract_summary",
    "governance_evidence_live_proof_readiness_gate_closed",
    "hermetic_governance_evidence_live_proof_readiness_check",
    "minimal_governance_evidence_live_proof_readiness_environ",
    "run_readiness_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "governance-evidence-live-proof-readiness"
PR_NUMBER = 164

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_governance_evidence_live_proof_readiness.py")
CHECKLIST_REL = Path("data/kilo_governance_evidence_live_proof_readiness/checklist.json")
FIXTURES_REL = Path("data/kilo_governance_evidence_live_proof_readiness/fixtures")
PR164_PASS_REL = Path("docs/audit/passes/2026-09-23-pr164.json")

PRIOR_GATE_IDS: tuple[str, ...] = (
    PRIOR_E2E_GATE_ID,
    GOVERNANCE_EVIDENCE_GATE_ID,
    "live-smoke-evidence",
    "live-proof-exec",
)

_REQUIRED_MARKERS: tuple[str, ...] = (
    GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_LABEL,
    "governance_evidence_hermetic_unit",
    "documented_founder_ack",
    "documented_box_url",
    "no_live_api_in_hermetic",
    FOUNDER_ACK_ENV,
    BOX_URL_ENV,
    "live_verified: false",
    "live_api_called: false",
    "four_state_max",
    "TEST_VERIFIED",
    GOVERNANCE_EVIDENCE_GATE_ID,
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/governance_evidence_live_proof_readiness.py"),
    Path("thinkbox/kilo_governance_evidence_live_proof_readiness.py"),
    Path("tests/unit/test_governance_evidence_live_proof_readiness.py"),
    Path("tests/unit/test_kilo_governance_evidence_live_proof_readiness_gate.py"),
    Path("tests/unit/test_kilo_live_proof_readiness_pr164.py"),
)


@dataclass(frozen=True)
class GovernanceEvidenceLiveProofReadinessViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class GovernanceEvidenceLiveProofReadinessEvidence:
    gate_id: str
    pr_number: int
    control_plane_e2e_deepen_ok: bool
    governance_evidence_ok: bool
    governance_evidence_hermetic_unit_ok: bool
    readiness_document_ok: bool
    fixture_suite_ok: bool
    live_api_called: bool = False
    live_verified: bool = False
    four_state_max: str = "TEST_VERIFIED"
    live_proof_prereqs_satisfied: bool = False


@dataclass(frozen=True)
class GovernanceEvidenceLiveProofReadinessResult:
    mode: EnvMatrixMode
    ok: bool
    control_plane_e2e_deepen_ok: bool
    governance_evidence_ok: bool
    violations: list[GovernanceEvidenceLiveProofReadinessViolation]
    evidence: GovernanceEvidenceLiveProofReadinessEvidence | None = None


def minimal_governance_evidence_live_proof_readiness_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_control_plane_e2e_deepen_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(
    doc: Mapping[str, Any],
) -> list[GovernanceEvidenceLiveProofReadinessViolation]:
    violations: list[GovernanceEvidenceLiveProofReadinessViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="checklist_gate_id",
                message="checklist gate_id mismatch",
                path=str(CHECKLIST_REL),
            ),
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="checklist_pr_number",
                message="checklist pr_number mismatch",
            ),
        )
    if doc.get("live_verified") is True:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="live_verified_true",
                message="live_verified must stay false",
            ),
        )
    if doc.get("live_api_called") is True:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="live_api_called_true",
                message="live_api_called must stay false",
            ),
        )
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="four_state",
                message="four_state_max must be TEST_VERIFIED",
            ),
        )
    if doc.get("governance_evidence_live_proof_readiness_version") != (
        GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_VERSION
    ):
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="version_mismatch",
                message="governance_evidence_live_proof_readiness_version",
            ),
        )
    prior = doc.get("prior_gate_ids") or []
    for required in (PRIOR_E2E_GATE_ID, GOVERNANCE_EVIDENCE_GATE_ID):
        if required not in prior:
            violations.append(
                GovernanceEvidenceLiveProofReadinessViolation(
                    code="prior_gate_missing",
                    message=f"must list {required}",
                ),
            )
    if doc.get("founder_ack_env_key") != FOUNDER_ACK_ENV:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="founder_ack_env_key",
                message=f"founder_ack_env_key must be {FOUNDER_ACK_ENV}",
            ),
        )
    if doc.get("box_url_env_key") != BOX_URL_ENV:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="box_url_env_key",
                message=f"box_url_env_key must be {BOX_URL_ENV}",
            ),
        )
    return violations


def _check_files() -> list[GovernanceEvidenceLiveProofReadinessViolation]:
    violations: list[GovernanceEvidenceLiveProofReadinessViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                GovernanceEvidenceLiveProofReadinessViolation(
                    code="module_missing",
                    message=f"missing {rel}",
                    path=str(rel),
                ),
            )
    if not (REPO_ROOT / VERIFY_SCRIPT_REL).is_file():
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="verify_script_missing",
                message=str(VERIFY_SCRIPT_REL),
            ),
        )
    guide = REPO_ROOT / Path("docs/guides/kilo_governance_evidence_live_proof_readiness.md")
    if not guide.is_file():
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="guide_missing",
                message=str(guide),
            ),
        )
    return violations


def _check_markers() -> list[GovernanceEvidenceLiveProofReadinessViolation]:
    violations: list[GovernanceEvidenceLiveProofReadinessViolation] = []
    blobs: list[str] = []
    for rel in (
        Path("docs/guides/kilo_governance_evidence_live_proof_readiness.md"),
        Path("thinkbox/governance_evidence_live_proof_readiness.py"),
        Path("thinkbox/kilo_governance_evidence_live_proof_readiness.py"),
    ):
        p = REPO_ROOT / rel
        if p.is_file():
            blobs.append(p.read_text(encoding="utf-8"))
    combined = "\n".join(blobs)
    for marker in _REQUIRED_MARKERS:
        if marker not in combined:
            violations.append(
                GovernanceEvidenceLiveProofReadinessViolation(
                    code="marker_missing",
                    message=f"missing marker {marker}",
                ),
            )
    return violations


def run_readiness_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = 0
    negative = 0

    snippet = governance_evidence_live_proof_readiness_contract_snippet()
    if snippet.get("live_verified") is False and snippet.get("live_api_called") is False:
        positive += 1
    else:
        errors.append("contract_snippet_honesty")

    minimal = minimal_valid_readiness_document(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        prior_gate_ids=list(PRIOR_GATE_IDS),
    )
    minimal_val = validate_readiness_document(minimal)
    if minimal_val.ok:
        positive += 1
    else:
        errors.append("minimal_readiness_document")

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if not fixtures_dir.is_dir():
        errors.append("fixtures_dir_missing")
        return positive, negative, errors

    for path in sorted(fixtures_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("expect_metadata_ok"):
            if (
                doc.get("founder_ack_documented")
                and doc.get("box_url_documented")
                and doc.get("live_verified") is False
                and doc.get("live_api_called") is False
            ):
                positive += 1
            else:
                errors.append(f"{path.name}: expect_metadata_ok failed")
            continue
        if doc.get("expect_ok"):
            val = validate_readiness_document(doc)
            if val.ok:
                positive += 1
            else:
                errors.append(f"{path.name}: expect_ok failed")
        if doc.get("expect_fail"):
            val = validate_readiness_document(doc)
            if not val.ok:
                negative += 1
            else:
                errors.append(f"{path.name}: expect_fail passed unexpectedly")

    return positive, negative, errors


def evaluate_governance_evidence_live_proof_readiness(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> GovernanceEvidenceLiveProofReadinessResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[GovernanceEvidenceLiveProofReadinessViolation] = []

    prior_e2e = hermetic_control_plane_e2e_deepen_check(env)
    if not prior_e2e.ok:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="prior_e2e_gate_failed",
                message=f"prior gate {PRIOR_E2E_GATE_ID} must pass",
            ),
        )

    gov_op = hermetic_governance_operator_check(env)
    governance_evidence_ok = gov_op.ok and governance_evidence_gate_closed()
    if not governance_evidence_ok:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="governance_evidence_gate_failed",
                message=f"layer {GOVERNANCE_EVIDENCE_GATE_ID} must pass",
            ),
        )

    hermetic_unit_ok, _unit_payload = evaluate_governance_evidence_hermetic_unit(env)
    if not hermetic_unit_ok:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="governance_evidence_hermetic_unit_failed",
                message="evaluate_governance_evidence hermetic_unit must pass",
            ),
        )

    if live_proof_prereqs_satisfied(env) and resolved in (
        EnvMatrixMode.HERMETIC_UNIT,
        EnvMatrixMode.HERMETIC_CI,
    ):
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="live_prereqs_in_hermetic",
                message="founder ack + Box URL must not satisfy live prep in hermetic modes",
            ),
        )

    violations.extend(_check_files())
    violations.extend(_check_markers())

    checklist_path = REPO_ROOT / CHECKLIST_REL
    readiness_doc_ok = False
    if checklist_path.is_file():
        doc = json.loads(checklist_path.read_text(encoding="utf-8"))
        checklist_violations = validate_checklist_document(doc)
        violations.extend(checklist_violations)
        readiness_doc_ok = len(checklist_violations) == 0
    else:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="checklist_missing",
                message="checklist missing",
            ),
        )

    pos, neg, fixture_errors = run_readiness_fixture_suite()
    for err in fixture_errors:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="fixture_failed",
                message=err,
            ),
        )
    fixture_ok = not fixture_errors and pos >= 2 and neg >= 1

    audit_path = REPO_ROOT / PR164_PASS_REL
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if audit.get("live_verified") is True:
            violations.append(
                GovernanceEvidenceLiveProofReadinessViolation(
                    code="audit_live_verified_true",
                    message="audit pass must keep live_verified false",
                ),
            )
        if audit.get("live_api_called") is True:
            violations.append(
                GovernanceEvidenceLiveProofReadinessViolation(
                    code="audit_live_api_called_true",
                    message="audit pass must keep live_api_called false",
                ),
            )
    else:
        violations.append(
            GovernanceEvidenceLiveProofReadinessViolation(
                code="audit_pass_missing",
                message=str(PR164_PASS_REL),
            ),
        )

    ok = (
        prior_e2e.ok
        and governance_evidence_ok
        and hermetic_unit_ok
        and readiness_doc_ok
        and fixture_ok
        and len(violations) == 0
    )
    evidence = GovernanceEvidenceLiveProofReadinessEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        control_plane_e2e_deepen_ok=prior_e2e.ok,
        governance_evidence_ok=governance_evidence_ok,
        governance_evidence_hermetic_unit_ok=hermetic_unit_ok,
        readiness_document_ok=readiness_doc_ok,
        fixture_suite_ok=fixture_ok,
        live_proof_prereqs_satisfied=live_proof_prereqs_satisfied(env),
    )
    return GovernanceEvidenceLiveProofReadinessResult(
        mode=resolved,
        ok=ok,
        control_plane_e2e_deepen_ok=prior_e2e.ok,
        governance_evidence_ok=governance_evidence_ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_governance_evidence_live_proof_readiness_check(
    environ: Mapping[str, str] | None = None,
) -> GovernanceEvidenceLiveProofReadinessResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_governance_evidence_live_proof_readiness(detect_matrix_mode(env), env)


def governance_evidence_live_proof_readiness_gate_closed() -> bool:
    return hermetic_governance_evidence_live_proof_readiness_check(
        minimal_governance_evidence_live_proof_readiness_environ()
    ).ok


def governance_evidence_live_proof_readiness_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_governance_evidence_live_proof_readiness_check(env)
    snippet = governance_evidence_live_proof_readiness_contract_snippet()
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr164_gate_id": GATE_ID,
        "pr162_layer_gate_id": PRIOR_E2E_GATE_ID,
        "governance_evidence_layer_gate_id": GOVERNANCE_EVIDENCE_GATE_ID,
        "governance_evidence_live_proof_readiness": GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_LABEL,
        "governance_evidence_live_proof_readiness_version": (
            GOVERNANCE_EVIDENCE_LIVE_PROOF_READINESS_VERSION
        ),
        "prior_gate_ids": list(PRIOR_GATE_IDS),
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "control_plane_e2e_deepen_ok": result.control_plane_e2e_deepen_ok,
        "governance_evidence_ok": result.governance_evidence_ok,
        "live_proof_prereqs_satisfied": live_proof_prereqs_satisfied(env),
        "founder_ack_env_key": FOUNDER_ACK_ENV,
        "box_url_env_key": BOX_URL_ENV,
        "live_api_called": False,
        "live_verified": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": governance_evidence_live_proof_readiness_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "fixtures_rel": str(FIXTURES_REL),
        "contract_snippet": snippet,
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
