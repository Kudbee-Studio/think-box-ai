"""Hermetic API / ops harden post-#166 gate (PR #167 theme B)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.api_ops_harden_post166 import (
    API_OPS_POST166_LABEL,
    API_OPS_POST166_VERSION,
    api_ops_post166_contract_snippet,
    build_post166_fail_closed_envelope,
    validate_post166_ops_envelope,
)
from thinkbox.kilo_api_ops_harden_post165 import (
    GATE_ID as POST165_OPS_GATE,
    hermetic_api_ops_harden_post165_check,
    minimal_api_ops_harden_post165_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_pr166_combined_post165_lane import (
    GATE_ID as PR166_GATE_ID,
    hermetic_pr166_combined_post165_lane_check,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ApiOpsPost166Evidence",
    "ApiOpsPost166Result",
    "ApiOpsPost166Violation",
    "api_ops_harden_post166_contract_summary",
    "api_ops_harden_post166_gate_closed",
    "evaluate_api_ops_harden_post166",
    "hermetic_api_ops_harden_post166_check",
    "minimal_api_ops_harden_post166_environ",
    "run_post166_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "api-ops-harden-post166"
PR_NUMBER = 167

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_api_ops_harden_post166.py")
CHECKLIST_REL = Path("data/kilo_api_ops_harden_post166/checklist.json")
FIXTURES_REL = Path("data/kilo_api_ops_harden_post166/fixtures")


@dataclass(frozen=True)
class ApiOpsPost166Violation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ApiOpsPost166Evidence:
    gate_id: str
    pr_number: int
    post165_ops_ok: bool
    pr166_combined_ok: bool
    envelope_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ApiOpsPost166Result:
    mode: EnvMatrixMode
    ok: bool
    violations: list[ApiOpsPost166Violation]
    evidence: ApiOpsPost166Evidence | None = None


def minimal_api_ops_harden_post166_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_api_ops_harden_post165_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ApiOpsPost166Violation]:
    violations: list[ApiOpsPost166Violation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(ApiOpsPost166Violation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ApiOpsPost166Violation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(ApiOpsPost166Violation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(ApiOpsPost166Violation(code="live_api", message="false"))
    if doc.get("post166_label") != API_OPS_POST166_LABEL:
        violations.append(ApiOpsPost166Violation(code="post166_label", message="label"))
    prior = doc.get("prior_gate_ids") or []
    for required in (POST165_OPS_GATE, PR166_GATE_ID):
        if required not in prior:
            violations.append(ApiOpsPost166Violation(code="prior_missing", message=required))
    return violations


def run_post166_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    env = build_post166_fail_closed_envelope(gate_id=GATE_ID, detail="fixture")
    if env.get("live_verified") is False:
        positive += 1
    else:
        errors.append("envelope_honesty")
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            _, errs = validate_post166_ops_envelope(doc)
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


def evaluate_api_ops_harden_post166(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ApiOpsPost166Result:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ApiOpsPost166Violation] = []

    post165 = hermetic_api_ops_harden_post165_check(env)
    if not post165.ok:
        violations.append(ApiOpsPost166Violation(code="post165_ops", message=POST165_OPS_GATE))
    pr166 = hermetic_pr166_combined_post165_lane_check(env)
    if not pr166.ok:
        violations.append(ApiOpsPost166Violation(code="pr166_combined", message=PR166_GATE_ID))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(ApiOpsPost166Violation(code="checklist_missing", message=""))

    pos, neg, fixture_errors = run_post166_fixture_suite()
    for err in fixture_errors:
        violations.append(ApiOpsPost166Violation(code="fixture", message=err))

    envelope_ok = pos >= 1 and not fixture_errors
    ok = post165.ok and pr166.ok and envelope_ok and len(violations) == 0
    evidence = ApiOpsPost166Evidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        post165_ops_ok=post165.ok,
        pr166_combined_ok=pr166.ok,
        envelope_ok=envelope_ok,
    )
    return ApiOpsPost166Result(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_api_ops_harden_post166_check(
    environ: Mapping[str, str] | None = None,
) -> ApiOpsPost166Result:
    env = environ if environ is not None else os.environ
    return evaluate_api_ops_harden_post166(detect_matrix_mode(env), env)


def api_ops_harden_post166_gate_closed() -> bool:
    return hermetic_api_ops_harden_post166_check(minimal_api_ops_harden_post166_environ()).ok


def api_ops_harden_post166_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_api_ops_harden_post166_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr167_theme_b_gate_id": GATE_ID,
        "post166_label": API_OPS_POST166_LABEL,
        "post166_version": API_OPS_POST166_VERSION,
        "prior_gate_ids": [POST165_OPS_GATE, PR166_GATE_ID],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": api_ops_harden_post166_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "contract_snippet": api_ops_post166_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
