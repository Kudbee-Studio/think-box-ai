"""Hermetic live-proof operator audit-flip post-#168 gate (PR #169 theme A)."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_hermetic_gate_memo import memoized_hermetic_check
from thinkbox.kilo_live_proof_operator_audit_flip_post167 import (
    GATE_ID as POST167_THEME_A_GATE,
)
from thinkbox.kilo_live_proof_operator_audit_flip_post167 import (
    hermetic_live_proof_operator_audit_flip_post167_check,
    minimal_live_proof_operator_audit_flip_post167_environ,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_live_smoke_audit_flip_harden import GATE_ID as AUDIT_FLIP_HARDEN_GATE
from thinkbox.kilo_live_smoke_evidence import GATE_ID as SMOKE_GATE_ID
from thinkbox.kilo_live_smoke_operator import GATE_ID as OPERATOR_GATE_ID
from thinkbox.live_proof_operator_audit_flip_post168 import (
    OPERATOR_AUDIT_FLIP_POST168_LABEL,
    OPERATOR_AUDIT_FLIP_POST168_VERSION,
    audit_flip_post168_contract_snippet,
    audit_flip_refused_post168_without_artifacts,
    operator_audit_flip_post168_checklist_items,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "OperatorAuditFlipPost168Evidence",
    "OperatorAuditFlipPost168Result",
    "OperatorAuditFlipPost168Violation",
    "evaluate_live_proof_operator_audit_flip_post168",
    "hermetic_live_proof_operator_audit_flip_post168_check",
    "live_proof_operator_audit_flip_post168_contract_summary",
    "live_proof_operator_audit_flip_post168_gate_closed",
    "minimal_live_proof_operator_audit_flip_post168_environ",
    "run_audit_flip_post168_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "live-proof-operator-audit-flip-post168"
PR_NUMBER = 169

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_live_proof_operator_audit_flip_post168.py")
CHECKLIST_REL = Path("data/kilo_live_proof_operator_audit_flip_post168/checklist.json")
FIXTURES_REL = Path("data/kilo_live_proof_operator_audit_flip_post168/fixtures")


@dataclass(frozen=True)
class OperatorAuditFlipPost168Violation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class OperatorAuditFlipPost168Evidence:
    gate_id: str
    pr_number: int
    post167_theme_a_ok: bool
    audit_flip_refused_ok: bool
    checklist_items_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class OperatorAuditFlipPost168Result:
    mode: EnvMatrixMode
    ok: bool
    violations: list[OperatorAuditFlipPost168Violation]
    evidence: OperatorAuditFlipPost168Evidence | None = None


def minimal_live_proof_operator_audit_flip_post168_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_live_proof_operator_audit_flip_post167_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(
    doc: Mapping[str, Any],
) -> list[OperatorAuditFlipPost168Violation]:
    violations: list[OperatorAuditFlipPost168Violation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(OperatorAuditFlipPost168Violation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(OperatorAuditFlipPost168Violation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(OperatorAuditFlipPost168Violation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(OperatorAuditFlipPost168Violation(code="live_api", message="false"))
    if doc.get("audit_flip_label") != OPERATOR_AUDIT_FLIP_POST168_LABEL:
        violations.append(
            OperatorAuditFlipPost168Violation(code="audit_flip_label", message="label")
        )
    prior = doc.get("prior_gate_ids") or []
    for required in (
        POST167_THEME_A_GATE,
        AUDIT_FLIP_HARDEN_GATE,
        OPERATOR_GATE_ID,
        SMOKE_GATE_ID,
    ):
        if required not in prior:
            violations.append(
                OperatorAuditFlipPost168Violation(code="prior_missing", message=required)
            )
    expected = doc.get("required_checklist_items")
    if expected != len(operator_audit_flip_post168_checklist_items()):
        violations.append(
            OperatorAuditFlipPost168Violation(code="checklist_count", message="count")
        )
    return violations


def run_audit_flip_post168_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    snippet = audit_flip_post168_contract_snippet()
    if snippet.get("audit_flip_refused_default") is True and snippet.get("live_verified") is False:
        positive += 1
    else:
        errors.append("snippet_fail_closed")
    if audit_flip_refused_post168_without_artifacts({}):
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


def evaluate_live_proof_operator_audit_flip_post168(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> OperatorAuditFlipPost168Result:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[OperatorAuditFlipPost168Violation] = []

    post167_theme = hermetic_live_proof_operator_audit_flip_post167_check(env)
    if not post167_theme.ok:
        violations.append(
            OperatorAuditFlipPost168Violation(code="post167_theme_a", message=POST167_THEME_A_GATE),
        )

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(OperatorAuditFlipPost168Violation(code="checklist_missing", message=""))

    pos, neg, fixture_errors = run_audit_flip_post168_fixture_suite()
    for err in fixture_errors:
        violations.append(OperatorAuditFlipPost168Violation(code="fixture", message=err))

    refused_ok = audit_flip_refused_post168_without_artifacts({})
    items_ok = len(operator_audit_flip_post168_checklist_items()) >= 32
    ok = (
        post167_theme.ok
        and refused_ok
        and items_ok
        and not fixture_errors
        and pos >= 2
        and len(violations) == 0
    )
    evidence = OperatorAuditFlipPost168Evidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        post167_theme_a_ok=post167_theme.ok,
        audit_flip_refused_ok=refused_ok,
        checklist_items_ok=items_ok,
    )
    return OperatorAuditFlipPost168Result(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_live_proof_operator_audit_flip_post168_check(
    environ: Mapping[str, str] | None = None,
) -> OperatorAuditFlipPost168Result:
    env = environ if environ is not None else os.environ
    return memoized_hermetic_check(
        GATE_ID,
        env,
        lambda: evaluate_live_proof_operator_audit_flip_post168(detect_matrix_mode(env), env),
    )


def live_proof_operator_audit_flip_post168_gate_closed() -> bool:
    return hermetic_live_proof_operator_audit_flip_post168_check(
        minimal_live_proof_operator_audit_flip_post168_environ(),
    ).ok


def live_proof_operator_audit_flip_post168_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_live_proof_operator_audit_flip_post168_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr169_theme_a_gate_id": GATE_ID,
        "audit_flip_label": OPERATOR_AUDIT_FLIP_POST168_LABEL,
        "audit_flip_version": OPERATOR_AUDIT_FLIP_POST168_VERSION,
        "prior_gate_ids": [POST167_THEME_A_GATE],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "audit_flip_refused_default": audit_flip_refused_post168_without_artifacts({}),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": result.ok,
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "contract_snippet": audit_flip_post168_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
