"""Hermetic live-proof operator prep deepen gate (PR #166 theme A)."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_live_smoke_audit_flip_harden import (
    GATE_ID as PRIOR_HARDEN_GATE_ID,
)
from thinkbox.kilo_live_smoke_audit_flip_harden import (
    hermetic_live_smoke_audit_flip_harden_check,
    minimal_live_smoke_audit_flip_harden_environ,
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
from thinkbox.live_proof_operator_prep_deepen import (
    OPERATOR_PREP_DEEPEN_LABEL,
    OPERATOR_PREP_DEEPEN_VERSION,
    founder_credential_readiness,
    operator_prep_checklist_items,
    operator_prep_contract_snippet,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "OperatorPrepDeepenEvidence",
    "OperatorPrepDeepenResult",
    "OperatorPrepDeepenViolation",
    "evaluate_live_proof_operator_prep_deepen",
    "hermetic_live_proof_operator_prep_deepen_check",
    "live_proof_operator_prep_deepen_contract_summary",
    "live_proof_operator_prep_deepen_gate_closed",
    "minimal_live_proof_operator_prep_deepen_environ",
    "run_operator_prep_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "live-proof-operator-prep-deepen"
PR_NUMBER = 166

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_live_proof_operator_prep_deepen.py")
CHECKLIST_REL = Path("data/kilo_live_proof_operator_prep_deepen/checklist.json")
FIXTURES_REL = Path("data/kilo_live_proof_operator_prep_deepen/fixtures")


@dataclass(frozen=True)
class OperatorPrepDeepenViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class OperatorPrepDeepenEvidence:
    gate_id: str
    pr_number: int
    smoke_evidence_ok: bool
    smoke_operator_ok: bool
    audit_flip_harden_ok: bool
    checklist_items_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class OperatorPrepDeepenResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[OperatorPrepDeepenViolation]
    evidence: OperatorPrepDeepenEvidence | None = None


def minimal_live_proof_operator_prep_deepen_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_live_smoke_audit_flip_harden_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[OperatorPrepDeepenViolation]:
    violations: list[OperatorPrepDeepenViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(OperatorPrepDeepenViolation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(OperatorPrepDeepenViolation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(OperatorPrepDeepenViolation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(OperatorPrepDeepenViolation(code="live_api", message="false"))
    if doc.get("prep_label") != OPERATOR_PREP_DEEPEN_LABEL:
        violations.append(OperatorPrepDeepenViolation(code="prep_label", message="label"))
    prior = doc.get("prior_gate_ids") or []
    for required in (SMOKE_GATE_ID, OPERATOR_GATE_ID, PRIOR_HARDEN_GATE_ID):
        if required not in prior:
            violations.append(OperatorPrepDeepenViolation(code="prior_missing", message=required))
    expected = doc.get("required_checklist_items")
    if expected != len(operator_prep_checklist_items()):
        violations.append(OperatorPrepDeepenViolation(code="checklist_count", message="count"))
    return violations


def run_operator_prep_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    snippet = operator_prep_contract_snippet()
    if snippet.get("live_verified") is False and snippet.get("founder_ready") is False:
        positive += 1
    else:
        errors.append("snippet_hermetic_not_ready")
    readiness = founder_credential_readiness({})
    if not readiness.ready_for_bounded_live_smoke and readiness.missing:
        positive += 1
    else:
        errors.append("readiness_fail_closed_empty_env")
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


def evaluate_live_proof_operator_prep_deepen(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> OperatorPrepDeepenResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[OperatorPrepDeepenViolation] = []

    smoke = hermetic_live_smoke_evidence_operator_check(env)
    if not smoke.ok:
        violations.append(OperatorPrepDeepenViolation(code="smoke_evidence", message=SMOKE_GATE_ID))
    op = hermetic_live_smoke_operator_check(env)
    if not op.ok:
        violations.append(
            OperatorPrepDeepenViolation(code="smoke_operator", message=OPERATOR_GATE_ID)
        )
    harden = hermetic_live_smoke_audit_flip_harden_check(env)
    if not harden.ok:
        violations.append(
            OperatorPrepDeepenViolation(code="audit_flip_harden", message=PRIOR_HARDEN_GATE_ID),
        )

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(OperatorPrepDeepenViolation(code="checklist_missing", message=""))

    pos, neg, fixture_errors = run_operator_prep_fixture_suite()
    for err in fixture_errors:
        violations.append(OperatorPrepDeepenViolation(code="fixture", message=err))

    items_ok = len(operator_prep_checklist_items()) >= 8
    ok = (
        smoke.ok
        and op.ok
        and harden.ok
        and items_ok
        and not fixture_errors
        and pos >= 2
        and len(violations) == 0
    )
    evidence = OperatorPrepDeepenEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        smoke_evidence_ok=smoke.ok,
        smoke_operator_ok=op.ok,
        audit_flip_harden_ok=harden.ok,
        checklist_items_ok=items_ok,
    )
    return OperatorPrepDeepenResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_live_proof_operator_prep_deepen_check(
    environ: Mapping[str, str] | None = None,
) -> OperatorPrepDeepenResult:
    env = environ if environ is not None else os.environ
    return evaluate_live_proof_operator_prep_deepen(detect_matrix_mode(env), env)


def live_proof_operator_prep_deepen_gate_closed() -> bool:
    return hermetic_live_proof_operator_prep_deepen_check(
        minimal_live_proof_operator_prep_deepen_environ(),
    ).ok


def live_proof_operator_prep_deepen_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_live_proof_operator_prep_deepen_check(env)
    readiness = founder_credential_readiness(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr166_theme_a_gate_id": GATE_ID,
        "prep_label": OPERATOR_PREP_DEEPEN_LABEL,
        "prep_version": OPERATOR_PREP_DEEPEN_VERSION,
        "prior_gate_ids": [SMOKE_GATE_ID, OPERATOR_GATE_ID, PRIOR_HARDEN_GATE_ID],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "founder_ready": readiness.ready_for_bounded_live_smoke,
        "missing_founder_env_keys": list(readiness.missing),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": live_proof_operator_prep_deepen_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "contract_snippet": operator_prep_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
