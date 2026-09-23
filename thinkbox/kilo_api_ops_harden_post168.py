"""Hermetic API / ops harden post-#168 gate (PR #169 theme B)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.api_ops_harden_post168 import (
    API_OPS_POST168_LABEL,
    API_OPS_POST168_VERSION,
    api_ops_post168_contract_snippet,
    build_post168_fail_closed_envelope,
    validate_post168_ops_envelope,
)
from thinkbox.kilo_api_ops_harden_post167 import (
    GATE_ID as POST167_OPS_GATE,
    hermetic_api_ops_harden_post167_check,
    minimal_api_ops_harden_post167_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_hermetic_gate_memo import memoized_hermetic_check
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ApiOpsPost168Evidence",
    "ApiOpsPost168Result",
    "ApiOpsPost168Violation",
    "api_ops_harden_post168_contract_summary",
    "api_ops_harden_post168_gate_closed",
    "evaluate_api_ops_harden_post168",
    "hermetic_api_ops_harden_post168_check",
    "minimal_api_ops_harden_post168_environ",
    "run_post168_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "api-ops-harden-post168"
PR_NUMBER = 169

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_api_ops_harden_post168.py")
CHECKLIST_REL = Path("data/kilo_api_ops_harden_post168/checklist.json")
FIXTURES_REL = Path("data/kilo_api_ops_harden_post168/fixtures")


@dataclass(frozen=True)
class ApiOpsPost168Violation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ApiOpsPost168Evidence:
    gate_id: str
    pr_number: int
    post167_ops_ok: bool
    envelope_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ApiOpsPost168Result:
    mode: EnvMatrixMode
    ok: bool
    violations: list[ApiOpsPost168Violation]
    evidence: ApiOpsPost168Evidence | None = None


def minimal_api_ops_harden_post168_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_api_ops_harden_post167_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ApiOpsPost168Violation]:
    violations: list[ApiOpsPost168Violation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(ApiOpsPost168Violation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(ApiOpsPost168Violation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(ApiOpsPost168Violation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(ApiOpsPost168Violation(code="live_api", message="false"))
    if doc.get("post168_label") != API_OPS_POST168_LABEL:
        violations.append(ApiOpsPost168Violation(code="post168_label", message="label"))
    prior = doc.get("prior_gate_ids") or []
    for required in (POST167_OPS_GATE,):
        if required not in prior:
            violations.append(ApiOpsPost168Violation(code="prior_missing", message=required))
    return violations


def run_post168_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    env = build_post168_fail_closed_envelope(gate_id=GATE_ID, detail="fixture")
    if env.get("live_verified") is False:
        positive += 1
    else:
        errors.append("envelope_honesty")
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            _, errs = validate_post168_ops_envelope(doc)
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


def evaluate_api_ops_harden_post168(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ApiOpsPost168Result:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ApiOpsPost168Violation] = []

    post167 = hermetic_api_ops_harden_post167_check(env)
    if not post167.ok:
        violations.append(ApiOpsPost168Violation(code="post167_ops", message=POST167_OPS_GATE))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(ApiOpsPost168Violation(code="checklist_missing", message=""))

    pos, neg, fixture_errors = run_post168_fixture_suite()
    for err in fixture_errors:
        violations.append(ApiOpsPost168Violation(code="fixture", message=err))

    envelope_ok = pos >= 1 and not fixture_errors
    ok = post167.ok and envelope_ok and len(violations) == 0
    evidence = ApiOpsPost168Evidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        post167_ops_ok=post167.ok,
        envelope_ok=envelope_ok,
    )
    return ApiOpsPost168Result(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_api_ops_harden_post168_check(
    environ: Mapping[str, str] | None = None,
) -> ApiOpsPost168Result:
    env = environ if environ is not None else os.environ
    return memoized_hermetic_check(
        GATE_ID,
        env,
        lambda: evaluate_api_ops_harden_post168(detect_matrix_mode(env), env),
    )


def api_ops_harden_post168_gate_closed() -> bool:
    return hermetic_api_ops_harden_post168_check(minimal_api_ops_harden_post168_environ()).ok


def api_ops_harden_post168_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_api_ops_harden_post168_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr169_theme_b_gate_id": GATE_ID,
        "post168_label": API_OPS_POST168_LABEL,
        "post168_version": API_OPS_POST168_VERSION,
        "prior_gate_ids": [POST167_OPS_GATE],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": result.ok,
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "contract_snippet": api_ops_post168_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
