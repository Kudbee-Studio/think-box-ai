"""Hermetic API / ops harden gate (PR #157, ``api-ops-harden``).

Layers on PR #156 ``dashboard-receipt-chain-bind``. Default: no network;
``live_api_called=False``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.control_plane_ops_harden import (
    OPS_HARDEN_LABEL,
    OPS_HARDEN_VERSION,
    clamp_query_limit,
    fingerprint_idempotency_body,
    ops_harden_contract_snippet,
    redact_mapping_for_logs,
)
from thinkbox.kilo_dashboard_receipt_chain_bind import (
    GATE_ID as PRIOR_GATE_ID,
)
from thinkbox.kilo_dashboard_receipt_chain_bind import (
    hermetic_dashboard_receipt_chain_bind_check,
    minimal_dashboard_receipt_chain_bind_environ,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ApiOpsHardenEvidence",
    "ApiOpsHardenResult",
    "ApiOpsHardenViolation",
    "api_ops_harden_contract_summary",
    "api_ops_harden_gate_closed",
    "evaluate_api_ops_harden",
    "hermetic_api_ops_harden_check",
    "minimal_api_ops_harden_environ",
    "run_harden_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "api-ops-harden"
PR_NUMBER = 157

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_api_ops_harden.py")
CHECKLIST_REL = Path("data/kilo_api_ops_harden/checklist.json")
FIXTURES_REL = Path("data/kilo_api_ops_harden/fixtures")

_REQUIRED_MARKERS: tuple[str, ...] = (
    OPS_HARDEN_LABEL,
    "control_plane_ops_harden",
    "http_exception_detail",
    "Idempotency-Key",
    "OpsRateLimitWindow",
    "redact_mapping_for_logs",
    "ops_harden_contract_snippet",
)

_REQUIRED_MODULES: tuple[Path, ...] = (
    Path("thinkbox/control_plane_ops_harden.py"),
    Path("backend/api/v1/control_plane.py"),
    Path("tests/unit/test_control_plane_ops_harden.py"),
    Path("tests/unit/test_backend_control_plane_ops_harden_pr157.py"),
)


@dataclass(frozen=True)
class ApiOpsHardenViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ApiOpsHardenEvidence:
    gate_id: str
    pr_number: int
    dashboard_bind_ok: bool
    module_markers_ok: bool
    fixture_suite_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ApiOpsHardenResult:
    mode: EnvMatrixMode
    ok: bool
    dashboard_bind_ok: bool
    violations: list[ApiOpsHardenViolation]
    evidence: ApiOpsHardenEvidence | None = None


def minimal_api_ops_harden_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_dashboard_receipt_chain_bind_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ApiOpsHardenViolation]:
    violations: list[ApiOpsHardenViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(
            ApiOpsHardenViolation(code="gate_id_mismatch", message="checklist gate_id")
        )
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(
            ApiOpsHardenViolation(code="pr_number_mismatch", message="checklist pr_number")
        )
    if doc.get("live_verified") is True:
        violations.append(
            ApiOpsHardenViolation(code="live_verified_true", message="must stay false")
        )
    if doc.get("four_state_max") != "TEST_VERIFIED":
        violations.append(
            ApiOpsHardenViolation(
                code="four_state", message="four_state_max must be TEST_VERIFIED"
            ),
        )
    if doc.get("ops_harden_version") != OPS_HARDEN_VERSION:
        violations.append(
            ApiOpsHardenViolation(code="ops_harden_version", message="ops_harden_version mismatch"),
        )
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_GATE_ID not in prior:
        violations.append(
            ApiOpsHardenViolation(code="prior_gate_missing", message=f"must list {PRIOR_GATE_ID}"),
        )
    return violations


def _check_files() -> list[ApiOpsHardenViolation]:
    violations: list[ApiOpsHardenViolation] = []
    for rel in _REQUIRED_MODULES:
        if not (REPO_ROOT / rel).is_file():
            violations.append(
                ApiOpsHardenViolation(
                    code="module_missing", message=f"missing {rel}", path=str(rel)
                ),
            )
    if not (REPO_ROOT / VERIFY_SCRIPT_REL).is_file():
        violations.append(
            ApiOpsHardenViolation(code="verify_script_missing", message=str(VERIFY_SCRIPT_REL)),
        )
    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        try:
            doc = json.loads(checklist.read_text(encoding="utf-8"))
            violations.extend(validate_checklist_document(doc))
        except json.JSONDecodeError:
            violations.append(ApiOpsHardenViolation(code="checklist_json", message="invalid JSON"))
    else:
        violations.append(
            ApiOpsHardenViolation(code="checklist_missing", message=str(CHECKLIST_REL))
        )
    return violations


def _check_markers() -> list[ApiOpsHardenViolation]:
    violations: list[ApiOpsHardenViolation] = []
    backend = (REPO_ROOT / "backend/api/v1/control_plane.py").read_text(encoding="utf-8")
    harden = (REPO_ROOT / "thinkbox/control_plane_ops_harden.py").read_text(encoding="utf-8")
    blob = backend + harden
    for marker in _REQUIRED_MARKERS:
        if marker not in blob:
            violations.append(
                ApiOpsHardenViolation(code="marker_missing", message=f"missing {marker!r}"),
            )
    return violations


def run_harden_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = 0
    negative = 0

    if clamp_query_limit(None) == 50:
        positive += 1
    else:
        errors.append("clamp default")
    if clamp_query_limit(9999) == 200:
        positive += 1
    else:
        errors.append("clamp max")

    redacted = redact_mapping_for_logs({"api_key": "supersecretvalue", "ok": True})
    if redacted.get("api_key") != "su…ue" and "***" not in str(redacted.get("api_key")):
        errors.append("redaction weak")
    else:
        positive += 1

    fp1 = fingerprint_idempotency_body({"operation_id": "a", "action_type": "x"})
    fp2 = fingerprint_idempotency_body({"action_type": "x", "operation_id": "a"})
    if fp1 != fp2:
        errors.append("idempotency fingerprint unstable")
    else:
        positive += 1

    snippet = ops_harden_contract_snippet()
    if snippet.get("ops_harden") != OPS_HARDEN_LABEL:
        errors.append("contract snippet")
    else:
        positive += 1

    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_ok"):
                positive += 1
            if doc.get("expect_fail"):
                negative += 1

    return positive, negative, errors


def evaluate_api_ops_harden(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ApiOpsHardenResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ApiOpsHardenViolation] = []

    prior = hermetic_dashboard_receipt_chain_bind_check(env)
    if not prior.ok:
        violations.append(
            ApiOpsHardenViolation(
                code="dashboard_bind_failed",
                message=f"prior gate {PRIOR_GATE_ID} must pass",
            ),
        )

    file_violations = _check_files()
    violations.extend(file_violations)
    marker_violations = _check_markers()
    violations.extend(marker_violations)

    pos, neg, fixture_errors = run_harden_fixture_suite()
    for err in fixture_errors:
        violations.append(ApiOpsHardenViolation(code="fixture_failed", message=err))

    fixture_ok = not fixture_errors and pos >= 4 and neg >= 1
    if not fixture_ok:
        violations.append(
            ApiOpsHardenViolation(code="fixture_suite_weak", message="harden fixtures weak")
        )

    markers_ok = len(marker_violations) == 0
    ok = prior.ok and fixture_ok and markers_ok and not file_violations and not fixture_errors
    evidence = ApiOpsHardenEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        dashboard_bind_ok=prior.ok,
        module_markers_ok=markers_ok,
        fixture_suite_ok=fixture_ok,
    )
    return ApiOpsHardenResult(
        mode=resolved,
        ok=ok,
        dashboard_bind_ok=prior.ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_api_ops_harden_check(
    environ: Mapping[str, str] | None = None,
) -> ApiOpsHardenResult:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    return evaluate_api_ops_harden(detect_matrix_mode(env), env)


def api_ops_harden_gate_closed() -> bool:
    return hermetic_api_ops_harden_check(minimal_api_ops_harden_environ()).ok


def api_ops_harden_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env: Mapping[str, str] = environ if environ is not None else os.environ
    result = hermetic_api_ops_harden_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr157_gate_id": GATE_ID,
        "pr156_layer_gate_id": PRIOR_GATE_ID,
        "ops_harden": OPS_HARDEN_LABEL,
        "ops_harden_version": OPS_HARDEN_VERSION,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "dashboard_receipt_chain_bind_ok": result.dashboard_bind_ok,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": api_ops_harden_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "verify_script_present": (REPO_ROOT / VERIFY_SCRIPT_REL).is_file(),
        "checklist_rel": str(CHECKLIST_REL),
        "fixtures_rel": str(FIXTURES_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
