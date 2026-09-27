"""Hermetic API / ops harden post-#165 gate (PR #166 theme B)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.api_ops_harden_post165 import (
    API_OPS_POST165_LABEL,
    API_OPS_POST165_VERSION,
    api_ops_post165_contract_snippet,
    build_post165_fail_closed_envelope,
    validate_post165_ops_envelope,
)
from thinkbox.kilo_api_ops_harden import (
    GATE_ID as API_OPS_GATE_ID,
    hermetic_api_ops_harden_check,
    minimal_api_ops_harden_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_pr165_combined_harden_era_chronicle import (
    GATE_ID as PR165_GATE_ID,
    hermetic_pr165_combined_harden_era_chronicle_check,
    minimal_pr165_combined_environ,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ApiOpsPost165Evidence",
    "ApiOpsPost165Result",
    "ApiOpsPost165Violation",
    "api_ops_harden_post165_contract_summary",
    "api_ops_harden_post165_gate_closed",
    "evaluate_api_ops_harden_post165",
    "hermetic_api_ops_harden_post165_check",
    "minimal_api_ops_harden_post165_environ",
    "run_post165_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "api-ops-harden-post165"
PR_NUMBER = 166

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_api_ops_harden_post165.py")
CHECKLIST_REL = Path("data/kilo_api_ops_harden_post165/checklist.json")
FIXTURES_REL = Path("data/kilo_api_ops_harden_post165/fixtures")


@dataclass(frozen=True)
class ApiOpsPost165Violation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ApiOpsPost165Evidence:
    gate_id: str
    pr_number: int
    api_ops_harden_ok: bool
    pr165_combined_ok: bool
    envelope_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ApiOpsPost165Result:
    mode: EnvMatrixMode
    ok: bool
    violations: list[ApiOpsPost165Violation]
    evidence: ApiOpsPost165Evidence | None = None


def minimal_api_ops_harden_post165_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_pr165_combined_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ApiOpsPost165Violation]:
    violations: list[ApiOpsPost165Violation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(ApiOpsPost165Violation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ApiOpsPost165Violation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(ApiOpsPost165Violation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(ApiOpsPost165Violation(code="live_api", message="false"))
    if doc.get("post165_label") != API_OPS_POST165_LABEL:
        violations.append(ApiOpsPost165Violation(code="post165_label", message="label"))
    prior = doc.get("prior_gate_ids") or []
    for required in (API_OPS_GATE_ID, PR165_GATE_ID):
        if required not in prior:
            violations.append(ApiOpsPost165Violation(code="prior_missing", message=required))
    return violations


def run_post165_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    env = build_post165_fail_closed_envelope(gate_id=GATE_ID, detail="fixture")
    if env.get("live_verified") is False:
        positive += 1
    else:
        errors.append("envelope_honesty")
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            _, errs = validate_post165_ops_envelope(doc)
            if doc.get("expect_valid"):
                if errs:
                    errors.append(f"{path.name}: {errs}")
                else:
                    positive += 1
            else:
                if errs:
                    negative += 1
                else:
                    errors.append(f"{path.name}: expected validation errors")
    return positive, negative, errors


def evaluate_api_ops_harden_post165(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ApiOpsPost165Result:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ApiOpsPost165Violation] = []

    api_ops = hermetic_api_ops_harden_check(env)
    if not api_ops.ok:
        violations.append(ApiOpsPost165Violation(code="api_ops_harden", message=API_OPS_GATE_ID))
    pr165 = hermetic_pr165_combined_harden_era_chronicle_check(env)
    if not pr165.ok:
        violations.append(ApiOpsPost165Violation(code="pr165_combined", message=PR165_GATE_ID))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(ApiOpsPost165Violation(code="checklist_missing", message=""))

    pos, neg, fixture_errors = run_post165_fixture_suite()
    for err in fixture_errors:
        violations.append(ApiOpsPost165Violation(code="fixture", message=err))

    envelope_ok = pos >= 1 and not fixture_errors
    ok = api_ops.ok and pr165.ok and envelope_ok and len(violations) == 0
    evidence = ApiOpsPost165Evidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        api_ops_harden_ok=api_ops.ok,
        pr165_combined_ok=pr165.ok,
        envelope_ok=envelope_ok,
    )
    return ApiOpsPost165Result(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_api_ops_harden_post165_check(
    environ: Mapping[str, str] | None = None,
) -> ApiOpsPost165Result:
    env = environ if environ is not None else os.environ
    return evaluate_api_ops_harden_post165(detect_matrix_mode(env), env)


def api_ops_harden_post165_gate_closed() -> bool:
    return hermetic_api_ops_harden_post165_check(minimal_api_ops_harden_post165_environ()).ok


def api_ops_harden_post165_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_api_ops_harden_post165_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr166_theme_b_gate_id": GATE_ID,
        "post165_label": API_OPS_POST165_LABEL,
        "post165_version": API_OPS_POST165_VERSION,
        "prior_gate_ids": [API_OPS_GATE_ID, PR165_GATE_ID],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": api_ops_harden_post165_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "contract_snippet": api_ops_post165_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
