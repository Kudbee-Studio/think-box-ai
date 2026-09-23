"""Hermetic control-plane API surface gate (PR #154, ``control-plane-api``).

Extends PR #153 live-smoke-operator with HTTP contract + route wiring checks.
Default path: no network; ``live_api_called=False``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_live_smoke_operator import (
    GATE_ID as OPERATOR_GATE_ID,
    hermetic_live_smoke_operator_check,
    minimal_live_smoke_operator_environ,
)

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ControlPlaneApiEvidence",
    "ControlPlaneApiResult",
    "ControlPlaneApiViolation",
    "control_plane_api_contract_summary",
    "control_plane_api_gate_closed",
    "evaluate_control_plane_api",
    "hermetic_control_plane_api_operator_check",
    "minimal_control_plane_api_environ",
    "run_contract_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "control-plane-api"
PR_NUMBER = 154

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_control_plane_api.py")
CHECKLIST_REL = Path("data/kilo_control_plane_api/checklist.json")
FIXTURES_REL = Path("data/kilo_control_plane_api/fixtures")

_REQUIRED_ROUTE_MARKERS: tuple[str, ...] = (
    '"/contract"',
    '"/operations"',
    '"/receipts/chain"',
    "require_control_plane_auth",
    "control_plane_api",
    "wrap_success",
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/control_plane_api_contract.py"),
    Path("thinkbox/control_plane_operation_registry.py"),
    Path("thinkbox/control_plane_hermetic_clients.py"),
    Path("thinkbox/control_plane_api_surface.py"),
    Path("backend/api/v1/control_plane.py"),
    Path("backend/api/v1/control_plane_auth.py"),
)


@dataclass(frozen=True)
class ControlPlaneApiViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ControlPlaneApiEvidence:
    gate_id: str
    pr_number: int
    operator_layer_ok: bool
    route_wiring_ok: bool
    contract_tests_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ControlPlaneApiResult:
    mode: EnvMatrixMode
    ok: bool
    operator_layer_ok: bool
    violations: list[ControlPlaneApiViolation]
    evidence: ControlPlaneApiEvidence | None = None


def minimal_control_plane_api_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_live_smoke_operator_environ())
    base.setdefault("THINKBOX_CONTROL_PLANE_ALLOW_DEV_TOKEN", "1")
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ControlPlaneApiViolation]:
    violations: list[ControlPlaneApiViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            ControlPlaneApiViolation(code="gate_id_mismatch", message="checklist gate_id")
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            ControlPlaneApiViolation(code="pr_number_mismatch", message="checklist pr_number")
        )
    if doc.get("live_verified") is True:
        violations.append(
            ControlPlaneApiViolation(code="live_verified_true", message="must stay false")
        )
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(
            ControlPlaneApiViolation(code="four_state", message="four_state_max must be TEST_VERIFIED")
        )
    return violations


def _check_files_present() -> list[ControlPlaneApiViolation]:
    violations: list[ControlPlaneApiViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                ControlPlaneApiViolation(
                    code="module_missing",
                    message=f"missing {rel}",
                    path=str(rel),
                )
            )
    verify = REPO_ROOT / VERIFY_SCRIPT_REL
    if not verify.is_file():
        violations.append(
            ControlPlaneApiViolation(
                code="verify_script_missing",
                message=f"missing {VERIFY_SCRIPT_REL}",
            )
        )
    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        try:
            doc = json.loads(checklist.read_text(encoding="utf-8"))
            violations.extend(validate_checklist_document(doc))
        except json.JSONDecodeError:
            violations.append(
                ControlPlaneApiViolation(code="checklist_json", message="invalid checklist JSON")
            )
    else:
        violations.append(
            ControlPlaneApiViolation(code="checklist_missing", message=f"missing {CHECKLIST_REL}")
        )
    return violations


def _check_route_wiring() -> list[ControlPlaneApiViolation]:
    violations: list[ControlPlaneApiViolation] = []
    main_text = (REPO_ROOT / "backend/main.py").read_text(encoding="utf-8")
    if "control_plane_api" not in main_text:
        violations.append(
            ControlPlaneApiViolation(code="main_router_missing", message="main.py must include control_plane_api")
        )
    cp_text = (REPO_ROOT / "backend/api/v1/control_plane.py").read_text(encoding="utf-8")
    for marker in _REQUIRED_ROUTE_MARKERS:
        if marker not in cp_text:
            violations.append(
                ControlPlaneApiViolation(
                    code="route_marker_missing",
                    message=f"missing marker {marker} in control_plane.py",
                )
            )
    return violations


def run_contract_fixture_suite() -> tuple[int, int, list[str]]:
    """Exercise contract validators (positive + negative cases)."""
    from thinkbox.control_plane_api_contract import (
        validate_operation_create_body,
        validate_required_fields,
    )

    errors: list[str] = []
    positive = 0
    negative = 0

    if not validate_required_fields({"a": "1"}, ("a",)):
        positive += 1
    else:
        errors.append("required fields positive case")

    bad = validate_required_fields({}, ("a",))
    if bad:
        negative += 1
    else:
        errors.append("required fields negative case")

    if not validate_operation_create_body(
        {"action_type": "demo", "operation_id": "op1"},
    ):
        positive += 1
    else:
        errors.append("operation body positive")

    if validate_operation_create_body({"action_type": "demo"}):
        negative += 1
    else:
        errors.append("operation body negative")

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            body = doc.get("body") or {}
            expect = doc.get("expect_violations", False)
            v = validate_operation_create_body(body)
            if expect and v:
                negative += 1
            elif not expect and not v:
                positive += 1
            else:
                errors.append(f"fixture {path.name} mismatch")
    return positive, negative, errors


def evaluate_control_plane_api(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ControlPlaneApiResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ControlPlaneApiViolation] = []

    operator = hermetic_live_smoke_operator_check(env)
    operator_ok = operator.ok
    if not operator_ok:
        violations.append(
            ControlPlaneApiViolation(
                code="operator_layer_failed",
                message=f"prior gate {OPERATOR_GATE_ID} must pass",
            )
        )

    file_violations = _check_files_present()
    route_violations = _check_route_wiring()
    violations.extend(file_violations)
    violations.extend(route_violations)

    pos, neg, fixture_errors = run_contract_fixture_suite()
    for err in fixture_errors:
        violations.append(ControlPlaneApiViolation(code="fixture_failed", message=err))

    contract_ok = not fixture_errors and pos >= 2 and neg >= 2
    if not contract_ok:
        violations.append(
            ControlPlaneApiViolation(code="contract_suite_weak", message="contract fixtures insufficient")
        )

    route_ok = len(route_violations) == 0 and "control_plane_api" in (
        REPO_ROOT / "backend/main.py"
    ).read_text(encoding="utf-8")

    evidence = ControlPlaneApiEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        operator_layer_ok=operator_ok,
        route_wiring_ok=route_ok,
        contract_tests_ok=contract_ok,
        live_api_called=False,
    )
    ok = (
        operator_ok
        and contract_ok
        and route_ok
        and not file_violations
        and not fixture_errors
    )
    return ControlPlaneApiResult(
        mode=resolved,
        ok=ok,
        operator_layer_ok=operator_ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_control_plane_api_operator_check(
    environ: Mapping[str, str] | None = None,
) -> ControlPlaneApiResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_control_plane_api(detect_matrix_mode(env), env)


def control_plane_api_gate_closed() -> bool:
    env = minimal_control_plane_api_environ()
    return hermetic_control_plane_api_operator_check(env).ok


def control_plane_api_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_control_plane_api_operator_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr154_gate_id": GATE_ID,
        "pr153_layer_gate_id": OPERATOR_GATE_ID,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "operator_layer_ok": result.operator_layer_ok,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": control_plane_api_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "fixtures_rel": str(FIXTURES_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
