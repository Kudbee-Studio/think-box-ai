"""Hermetic live-proof operator audit-flip deepen gate (PR #167 theme A)."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_operator_prep_deepen import (
    GATE_ID as PREP_DEEPEN_GATE,
)
from thinkbox.kilo_live_proof_operator_prep_deepen import (
    hermetic_live_proof_operator_prep_deepen_check,
    minimal_live_proof_operator_prep_deepen_environ,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_live_smoke_audit_flip_harden import (
    GATE_ID as AUDIT_FLIP_HARDEN_GATE,
)
from thinkbox.kilo_live_smoke_audit_flip_harden import (
    hermetic_live_smoke_audit_flip_harden_check,
)
from thinkbox.kilo_live_smoke_evidence import (
    GATE_ID as SMOKE_GATE_ID,
)
from thinkbox.kilo_live_smoke_evidence import (
    hermetic_live_smoke_evidence_operator_check,
)
from thinkbox.kilo_live_smoke_operator import (
    GATE_ID as OPERATOR_GATE_ID,
)
from thinkbox.kilo_live_smoke_operator import (
    hermetic_live_smoke_operator_check,
)
from thinkbox.kilo_pr166_combined_post165_lane import (
    GATE_ID as PR166_GATE_ID,
)
from thinkbox.kilo_pr166_combined_post165_lane import (
    hermetic_pr166_combined_post165_lane_check,
)
from thinkbox.live_proof_operator_audit_flip_deepen import (
    OPERATOR_AUDIT_FLIP_DEEPEN_LABEL,
    OPERATOR_AUDIT_FLIP_DEEPEN_VERSION,
    audit_flip_deepen_contract_snippet,
    audit_flip_refused_without_artifacts,
    operator_audit_flip_checklist_items,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "OperatorAuditFlipDeepenEvidence",
    "OperatorAuditFlipDeepenResult",
    "OperatorAuditFlipDeepenViolation",
    "evaluate_live_proof_operator_audit_flip_deepen",
    "hermetic_live_proof_operator_audit_flip_deepen_check",
    "live_proof_operator_audit_flip_deepen_contract_summary",
    "live_proof_operator_audit_flip_deepen_gate_closed",
    "minimal_live_proof_operator_audit_flip_deepen_environ",
    "run_audit_flip_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "live-proof-operator-audit-flip-deepen"
PR_NUMBER = 167

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_live_proof_operator_audit_flip_deepen.py")
CHECKLIST_REL = Path("data/kilo_live_proof_operator_audit_flip_deepen/checklist.json")
FIXTURES_REL = Path("data/kilo_live_proof_operator_audit_flip_deepen/fixtures")


@dataclass(frozen=True)
class OperatorAuditFlipDeepenViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class OperatorAuditFlipDeepenEvidence:
    gate_id: str
    pr_number: int
    prep_deepen_ok: bool
    pr166_combined_ok: bool
    audit_flip_refused_ok: bool
    checklist_items_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class OperatorAuditFlipDeepenResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[OperatorAuditFlipDeepenViolation]
    evidence: OperatorAuditFlipDeepenEvidence | None = None


def minimal_live_proof_operator_audit_flip_deepen_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_live_proof_operator_prep_deepen_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(
    doc: Mapping[str, Any],
) -> list[OperatorAuditFlipDeepenViolation]:
    violations: list[OperatorAuditFlipDeepenViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(OperatorAuditFlipDeepenViolation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(OperatorAuditFlipDeepenViolation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(OperatorAuditFlipDeepenViolation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(OperatorAuditFlipDeepenViolation(code="live_api", message="false"))
    if doc.get("audit_flip_label") != OPERATOR_AUDIT_FLIP_DEEPEN_LABEL:
        violations.append(
            OperatorAuditFlipDeepenViolation(code="audit_flip_label", message="label")
        )
    prior = doc.get("prior_gate_ids") or []
    for required in (
        PREP_DEEPEN_GATE,
        AUDIT_FLIP_HARDEN_GATE,
        OPERATOR_GATE_ID,
        SMOKE_GATE_ID,
    ):
        if required not in prior:
            violations.append(
                OperatorAuditFlipDeepenViolation(code="prior_missing", message=required)
            )
    expected = doc.get("required_checklist_items")
    if expected != len(operator_audit_flip_checklist_items()):
        violations.append(OperatorAuditFlipDeepenViolation(code="checklist_count", message="count"))
    return violations


def run_audit_flip_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    snippet = audit_flip_deepen_contract_snippet()
    if snippet.get("audit_flip_refused_default") is True and snippet.get("live_verified") is False:
        positive += 1
    else:
        errors.append("snippet_fail_closed")
    if audit_flip_refused_without_artifacts({}):
        positive += 1
    else:
        errors.append("refused_empty_evidence")
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_ready") is False:
                if doc.get("live_verified") is True:
                    errors.append(f"{path.name}: live_verified must be false")
                else:
                    negative += 1
    return positive, negative, errors


def evaluate_live_proof_operator_audit_flip_deepen(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> OperatorAuditFlipDeepenResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[OperatorAuditFlipDeepenViolation] = []

    prep = hermetic_live_proof_operator_prep_deepen_check(env)
    if not prep.ok:
        violations.append(
            OperatorAuditFlipDeepenViolation(code="prep_deepen", message=PREP_DEEPEN_GATE)
        )
    pr166 = hermetic_pr166_combined_post165_lane_check(env)
    if not pr166.ok:
        violations.append(
            OperatorAuditFlipDeepenViolation(code="pr166_combined", message=PR166_GATE_ID)
        )
    smoke = hermetic_live_smoke_evidence_operator_check(env)
    if not smoke.ok:
        violations.append(
            OperatorAuditFlipDeepenViolation(code="smoke_evidence", message=SMOKE_GATE_ID)
        )
    op = hermetic_live_smoke_operator_check(env)
    if not op.ok:
        violations.append(
            OperatorAuditFlipDeepenViolation(code="smoke_operator", message=OPERATOR_GATE_ID)
        )
    harden = hermetic_live_smoke_audit_flip_harden_check(env)
    if not harden.ok:
        violations.append(
            OperatorAuditFlipDeepenViolation(
                code="audit_flip_harden", message=AUDIT_FLIP_HARDEN_GATE
            ),
        )

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(OperatorAuditFlipDeepenViolation(code="checklist_missing", message=""))

    pos, neg, fixture_errors = run_audit_flip_fixture_suite()
    for err in fixture_errors:
        violations.append(OperatorAuditFlipDeepenViolation(code="fixture", message=err))

    refused_ok = audit_flip_refused_without_artifacts({})
    items_ok = len(operator_audit_flip_checklist_items()) >= 16
    ok = (
        prep.ok
        and pr166.ok
        and smoke.ok
        and op.ok
        and harden.ok
        and refused_ok
        and items_ok
        and not fixture_errors
        and pos >= 2
        and len(violations) == 0
    )
    evidence = OperatorAuditFlipDeepenEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        prep_deepen_ok=prep.ok,
        pr166_combined_ok=pr166.ok,
        audit_flip_refused_ok=refused_ok,
        checklist_items_ok=items_ok,
    )
    return OperatorAuditFlipDeepenResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_live_proof_operator_audit_flip_deepen_check(
    environ: Mapping[str, str] | None = None,
) -> OperatorAuditFlipDeepenResult:
    env = environ if environ is not None else os.environ
    return evaluate_live_proof_operator_audit_flip_deepen(detect_matrix_mode(env), env)


def live_proof_operator_audit_flip_deepen_gate_closed() -> bool:
    return hermetic_live_proof_operator_audit_flip_deepen_check(
        minimal_live_proof_operator_audit_flip_deepen_environ(),
    ).ok


def live_proof_operator_audit_flip_deepen_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_live_proof_operator_audit_flip_deepen_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr167_theme_a_gate_id": GATE_ID,
        "audit_flip_label": OPERATOR_AUDIT_FLIP_DEEPEN_LABEL,
        "audit_flip_version": OPERATOR_AUDIT_FLIP_DEEPEN_VERSION,
        "prior_gate_ids": [PREP_DEEPEN_GATE, PR166_GATE_ID],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "audit_flip_refused_default": audit_flip_refused_without_artifacts({}),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": live_proof_operator_audit_flip_deepen_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "contract_snippet": audit_flip_deepen_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
