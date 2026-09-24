"""Hermetic beyond-KILO lint readiness gate (PR #170 — ruff, mypy, bandit).

Self-contained lane: not a combined post-#N umbrella. Prior gates referenced by id only.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.beyond_kilo_lint import (
    BEYOND_KILO_LINT_LABEL,
    BEYOND_KILO_LINT_VERSION,
    beyond_kilo_lint_contract_snippet,
    execute_beyond_kilo_lint_suite,
    lint_execution_enabled,
    lint_results_to_json,
    pyproject_lint_sections_present,
    validate_lint_scope_paths,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_hermetic_gate_memo import memoized_hermetic_check
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_pr169_combined_post168_lane import GATE_ID as PRIOR_UMBRELLA_GATE_ID

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR170_PASS_REL",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "BeyondKiloLintEvidence",
    "BeyondKiloLintResult",
    "BeyondKiloLintViolation",
    "beyond_kilo_lint_contract_summary",
    "beyond_kilo_lint_gate_closed",
    "evaluate_beyond_kilo_lint",
    "hermetic_beyond_kilo_lint_check",
    "minimal_beyond_kilo_lint_environ",
    "run_beyond_kilo_lint_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "beyond-kilo-lint-readiness"
PR_NUMBER = 170

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_beyond_kilo_lint.py")
CHECKLIST_REL = Path("data/kilo_beyond_kilo_lint/checklist.json")
FIXTURES_REL = Path("data/kilo_beyond_kilo_lint/fixtures")
PR170_PASS_REL = Path("docs/audit/passes/2026-09-23-pr170.json")


@dataclass(frozen=True)
class BeyondKiloLintViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class BeyondKiloLintEvidence:
    gate_id: str
    pr_number: int
    static_ok: bool
    lint_executed: bool
    lint_tools_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class BeyondKiloLintResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[BeyondKiloLintViolation]
    evidence: BeyondKiloLintEvidence | None = None


def minimal_beyond_kilo_lint_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = {
        "THINKBOX_KILO_HERMETIC": "1",
        "KILO_BEYOND_KILO_LINT_REQUIRE_TOOLS": "0",
        "KILO_BEYOND_KILO_LINT_EXECUTE": "0",
    }
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[BeyondKiloLintViolation]:
    violations: list[BeyondKiloLintViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(BeyondKiloLintViolation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(BeyondKiloLintViolation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(BeyondKiloLintViolation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(BeyondKiloLintViolation(code="live_api", message="false"))
    if doc.get("beyond_kilo_label") != BEYOND_KILO_LINT_LABEL:
        violations.append(BeyondKiloLintViolation(code="label", message="beyond_kilo_label"))
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_UMBRELLA_GATE_ID not in prior:
        violations.append(
            BeyondKiloLintViolation(
                code="prior_missing",
                message=PRIOR_UMBRELLA_GATE_ID,
            ),
        )
    tools = doc.get("lint_tools") or []
    for required in ("ruff", "mypy", "bandit"):
        if required not in tools:
            violations.append(BeyondKiloLintViolation(code="lint_tools", message=required))
    return violations


def run_beyond_kilo_lint_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = negative = 0
    snippet = beyond_kilo_lint_contract_snippet()
    if snippet.get("live_verified") is False:
        positive += 1
    else:
        errors.append("snippet_honesty")
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_valid"):
                if doc.get("gate_id") == GATE_ID and doc.get("live_verified") is False:
                    positive += 1
                else:
                    errors.append(f"{path.name}: expected valid honesty")
            else:
                if doc.get("live_verified") is True:
                    negative += 1
                else:
                    errors.append(f"{path.name}: expected invalid live_verified")
    return positive, negative, errors


def evaluate_beyond_kilo_lint(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> BeyondKiloLintResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[BeyondKiloLintViolation] = []

    for scope_v in validate_lint_scope_paths():
        violations.append(
            BeyondKiloLintViolation(code=scope_v.code, message=scope_v.message),
        )

    sections_ok, missing_sections = pyproject_lint_sections_present()
    if not sections_ok:
        for item in missing_sections:
            violations.append(BeyondKiloLintViolation(code="pyproject", message=item))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(BeyondKiloLintViolation(code="checklist_missing", message=""))

    if not (REPO_ROOT / VERIFY_SCRIPT_REL).is_file():
        violations.append(BeyondKiloLintViolation(code="verify_script", message="missing"))

    pos, neg, fixture_errors = run_beyond_kilo_lint_fixture_suite()
    for err in fixture_errors:
        violations.append(BeyondKiloLintViolation(code="fixture", message=err))

    fixture_ok = pos >= 1 and not fixture_errors
    static_ok = len(violations) == 0 and fixture_ok

    lint_executed = lint_execution_enabled(env)
    lint_violations: list[BeyondKiloLintViolation] = []
    if lint_executed:
        _, lint_raw = execute_beyond_kilo_lint_suite(env)
        for lv in lint_raw:
            lint_violations.append(
                BeyondKiloLintViolation(code=lv.code, message=lv.message, path=lv.tool),
            )
    violations.extend(lint_violations)

    lint_tools_ok = True
    if lint_executed:
        lint_tools_ok = not any(v.code in ("tool_failed", "tool_missing") for v in lint_violations)

    ok = static_ok and (not lint_executed or lint_tools_ok)
    evidence = BeyondKiloLintEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        static_ok=static_ok and fixture_ok,
        lint_executed=lint_executed,
        lint_tools_ok=lint_tools_ok if lint_executed else True,
    )
    return BeyondKiloLintResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_beyond_kilo_lint_check(
    environ: Mapping[str, str] | None = None,
) -> BeyondKiloLintResult:
    env = environ if environ is not None else os.environ
    return memoized_hermetic_check(
        GATE_ID,
        env,
        lambda: evaluate_beyond_kilo_lint(detect_matrix_mode(env), env),
    )


def beyond_kilo_lint_gate_closed() -> bool:
    return hermetic_beyond_kilo_lint_check(minimal_beyond_kilo_lint_environ()).ok


def beyond_kilo_lint_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_beyond_kilo_lint_check(env)
    sections_ok, _ = pyproject_lint_sections_present()
    lint_runs, _ = execute_beyond_kilo_lint_suite(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr170_gate_id": GATE_ID,
        "beyond_kilo_label": BEYOND_KILO_LINT_LABEL,
        "beyond_kilo_version": BEYOND_KILO_LINT_VERSION,
        "prior_gate_ids": [PRIOR_UMBRELLA_GATE_ID],
        "lint_tools": ["ruff", "mypy", "bandit"],
        "lint_execution_enabled": lint_execution_enabled(env),
        "lint_tools_required": env.get("CI", "").lower() in ("1", "true")
        or env.get("KILO_BEYOND_KILO_LINT_REQUIRE_TOOLS", "").lower() in ("1", "true"),
        "pyproject_lint_sections_ok": sections_ok,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": result.ok,
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "contract_snippet": beyond_kilo_lint_contract_snippet(),
        "lint_run_summary": lint_results_to_json(lint_runs),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
        "combined_umbrella_nested": False,
    }
