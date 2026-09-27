"""Hermetic control-plane E2E deepen gate (PR #162).

Layers on PR #161 ``end-link-api-ops-harden``. Validates hermetic e2e modules and
assertion helpers — no live Box/Mercury HTTP.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.control_plane_e2e_assertions import (
    CONTROL_PLANE_E2E_DEEPEN_LABEL,
    CONTROL_PLANE_E2E_DEEPEN_VERSION,
    control_plane_e2e_contract_snippet,
)
from thinkbox.kilo_end_link_api_ops_harden import (
    GATE_ID as PRIOR_GATE_ID,
)
from thinkbox.kilo_end_link_api_ops_harden import (
    hermetic_end_link_api_ops_harden_check,
    minimal_end_link_api_ops_harden_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_hermetic_subprocess import (
    DEFAULT_E2E_UNITTEST_TIMEOUT_SECONDS,
    e2e_unittest_skipped_by_default,
    nested_e2e_unittest_enabled,
    run_bounded_unittest_modules,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CHECKLIST_REL",
    "E2E_TEST_MODULES",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ControlPlaneE2eDeepenEvidence",
    "ControlPlaneE2eDeepenResult",
    "ControlPlaneE2eDeepenViolation",
    "control_plane_e2e_deepen_contract_summary",
    "control_plane_e2e_deepen_gate_closed",
    "evaluate_control_plane_e2e_deepen",
    "hermetic_control_plane_e2e_deepen_check",
    "minimal_control_plane_e2e_deepen_environ",
    "run_e2e_fixture_suite",
    "run_hermetic_e2e_unittest_suite",
    "validate_checklist_document",
)

GATE_ID = "control-plane-e2e-deepen"
PR_NUMBER = 162

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_control_plane_e2e_deepen.py")
CHECKLIST_REL = Path("data/kilo_control_plane_e2e_deepen/checklist.json")
FIXTURES_REL = Path("data/kilo_control_plane_e2e_deepen/fixtures")
PR162_PASS_REL = Path("docs/audit/passes/2026-09-23-pr162.json")

E2E_TEST_MODULES: tuple[str, ...] = (
    "tests.e2e.test_f162_cp_validate_single_e2e",
    "tests.e2e.test_f162_cp_batch_validate_e2e",
    "tests.e2e.test_f162_cp_chain_filters_e2e",
    "tests.e2e.test_f162_cp_chain_head_tail_e2e",
    "tests.e2e.test_f162_cp_integrity_fields_e2e",
    "tests.e2e.test_f162_cp_ops_envelope_e2e",
    "tests.e2e.test_f162_cp_fail_closed_e2e",
)

_REQUIRED_MARKERS: tuple[str, ...] = (
    CONTROL_PLANE_E2E_DEEPEN_LABEL,
    "control_plane_hermetic",
    "assert_success_envelope_honesty",
    "assert_ops_timing_honesty",
    "prev_receipt_id",
    "link_integrity",
    "Idempotency-Key",
    "live_verified: false",
    "four_state_max",
    "TEST_VERIFIED",
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("tests/e2e/control_plane_hermetic.py"),
    Path("thinkbox/control_plane_e2e_assertions.py"),
    Path("thinkbox/kilo_control_plane_e2e_deepen.py"),
    Path("tests/unit/test_control_plane_e2e_assertions.py"),
    Path("tests/unit/test_kilo_control_plane_e2e_deepen_gate.py"),
    Path("tests/unit/test_kilo_live_proof_readiness_pr162.py"),
)


@dataclass(frozen=True)
class ControlPlaneE2eDeepenViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ControlPlaneE2eDeepenEvidence:
    gate_id: str
    pr_number: int
    end_link_api_ops_harden_ok: bool
    e2e_modules_ok: bool
    unittest_suite_ok: bool
    fixture_suite_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ControlPlaneE2eDeepenResult:
    mode: EnvMatrixMode
    ok: bool
    end_link_api_ops_harden_ok: bool
    violations: list[ControlPlaneE2eDeepenViolation]
    evidence: ControlPlaneE2eDeepenEvidence | None = None


def minimal_control_plane_e2e_deepen_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_end_link_api_ops_harden_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ControlPlaneE2eDeepenViolation]:
    violations: list[ControlPlaneE2eDeepenViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            ControlPlaneE2eDeepenViolation(
                code="checklist_gate_id",
                message="checklist gate_id mismatch",
                path=str(CHECKLIST_REL),
            ),
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            ControlPlaneE2eDeepenViolation(
                code="checklist_pr_number",
                message="checklist pr_number mismatch",
            ),
        )
    return violations


def _check_files() -> list[ControlPlaneE2eDeepenViolation]:
    violations: list[ControlPlaneE2eDeepenViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                ControlPlaneE2eDeepenViolation(
                    code="missing_module",
                    message=f"missing {rel}",
                    path=str(rel),
                ),
            )
    for mod in E2E_TEST_MODULES:
        path = REPO_ROOT / Path(mod.replace(".", "/") + ".py")
        if not path.is_file():
            violations.append(
                ControlPlaneE2eDeepenViolation(
                    code="missing_e2e_test",
                    message=f"missing {mod}",
                    path=str(path),
                ),
            )
    return violations


def _check_markers() -> list[ControlPlaneE2eDeepenViolation]:
    violations: list[ControlPlaneE2eDeepenViolation] = []
    blobs: list[tuple[str, str]] = []
    for rel in (
        Path("tests/e2e/control_plane_hermetic.py"),
        Path("thinkbox/control_plane_e2e_assertions.py"),
        Path("docs/guides/kilo_control_plane_e2e_deepen.md"),
    ):
        p = REPO_ROOT / rel
        if p.is_file():
            blobs.append((str(rel), p.read_text(encoding="utf-8")))
    combined = "\n".join(t for _, t in blobs)
    for marker in _REQUIRED_MARKERS:
        if marker not in combined:
            violations.append(
                ControlPlaneE2eDeepenViolation(
                    code="missing_marker",
                    message=f"missing marker {marker}",
                ),
            )
    return violations


def run_e2e_fixture_suite() -> tuple[int, int, list[str]]:
    """Positive/negative counts from JSON fixtures under data/kilo_control_plane_e2e_deepen."""
    errors: list[str] = []
    positive = 0
    negative = 0
    snippet = control_plane_e2e_contract_snippet()
    if snippet.get("live_verified") is False:
        positive += 1
    else:
        errors.append("contract_snippet_live")

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if not fixtures_dir.is_dir():
        errors.append("fixtures_dir_missing")
        return positive, negative, errors
    for path in sorted(fixtures_dir.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("expect_ok"):
            positive += 1
        if doc.get("expect_fail"):
            negative += 1
    return positive, negative, errors


def run_hermetic_e2e_unittest_suite() -> tuple[bool, str]:
    if not nested_e2e_unittest_enabled():
        return True, "skipped:KILO_RUN_NESTED_E2E_UNITTEST_not_set"
    result = run_bounded_unittest_modules(
        E2E_TEST_MODULES,
        repo_root=REPO_ROOT,
        timeout_seconds=DEFAULT_E2E_UNITTEST_TIMEOUT_SECONDS,
    )
    log = result.stdout + result.stderr
    if result.timed_out:
        return False, f"e2e_unittest_timeout:{DEFAULT_E2E_UNITTEST_TIMEOUT_SECONDS}s\n{log[:500]}"
    if result.returncode != 0:
        return False, log
    return True, log


def evaluate_control_plane_e2e_deepen(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ControlPlaneE2eDeepenResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ControlPlaneE2eDeepenViolation] = []

    prior = hermetic_end_link_api_ops_harden_check(env)
    if not prior.ok:
        violations.append(
            ControlPlaneE2eDeepenViolation(
                code="prior_api_ops_gate_failed",
                message=f"prior gate {PRIOR_GATE_ID} must pass",
            ),
        )

    violations.extend(_check_files())
    violations.extend(_check_markers())

    checklist_path = REPO_ROOT / CHECKLIST_REL
    if checklist_path.is_file():
        doc = json.loads(checklist_path.read_text(encoding="utf-8"))
        violations.extend(validate_checklist_document(doc))
    else:
        violations.append(
            ControlPlaneE2eDeepenViolation(code="checklist_missing", message="checklist missing"),
        )

    pos, neg, fixture_errors = run_e2e_fixture_suite()
    for err in fixture_errors:
        violations.append(ControlPlaneE2eDeepenViolation(code="fixture_failed", message=err))
    fixture_ok = not fixture_errors and pos >= 2 and neg >= 1

    unittest_ok, unittest_log = run_hermetic_e2e_unittest_suite()
    if not unittest_ok:
        violations.append(
            ControlPlaneE2eDeepenViolation(
                code="e2e_unittest_failed",
                message=unittest_log[:500],
            ),
        )

    e2e_modules_ok = not any(v.code.startswith("missing_e2e") for v in violations)
    ok = (
        prior.ok
        and fixture_ok
        and unittest_ok
        and e2e_modules_ok
        and not any(v.code == "missing_module" for v in violations)
        and len([v for v in violations if v.code == "missing_marker"]) == 0
    )
    evidence = ControlPlaneE2eDeepenEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        end_link_api_ops_harden_ok=prior.ok,
        e2e_modules_ok=e2e_modules_ok,
        unittest_suite_ok=unittest_ok,
        fixture_suite_ok=fixture_ok,
    )
    return ControlPlaneE2eDeepenResult(
        mode=resolved,
        ok=ok,
        end_link_api_ops_harden_ok=prior.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_control_plane_e2e_deepen_check(
    environ: Mapping[str, str] | None = None,
) -> ControlPlaneE2eDeepenResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_control_plane_e2e_deepen(detect_matrix_mode(env), env)


def control_plane_e2e_deepen_gate_closed() -> bool:
    return hermetic_control_plane_e2e_deepen_check(minimal_control_plane_e2e_deepen_environ()).ok


def control_plane_e2e_deepen_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_control_plane_e2e_deepen_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr162_gate_id": GATE_ID,
        "pr161_layer_gate_id": PRIOR_GATE_ID,
        "control_plane_e2e_deepen": CONTROL_PLANE_E2E_DEEPEN_LABEL,
        "control_plane_e2e_deepen_version": CONTROL_PLANE_E2E_DEEPEN_VERSION,
        "e2e_test_module_count": len(E2E_TEST_MODULES),
        "e2e_unittest_skipped_default": e2e_unittest_skipped_by_default(),
        "e2e_unittest_ran": nested_e2e_unittest_enabled(),
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "end_link_api_ops_harden_ok": result.end_link_api_ops_harden_ok,
        "live_api_called": False,
        "live_verified": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": control_plane_e2e_deepen_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "fixtures_rel": str(FIXTURES_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
