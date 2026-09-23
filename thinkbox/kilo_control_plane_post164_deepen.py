"""Hermetic control-plane post-#164 deepen gate (PR #165 theme B)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.control_plane_post164_deepen import (
    POST164_DEEPEN_LABEL,
    POST164_DEEPEN_VERSION,
    assert_hermetic_control_plane_response,
    control_plane_post164_contract_snippet,
    post164_deepen_markers_present,
    validate_post164_request_envelope,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    GATE_ID as PRIOR_GATE_ID,
    hermetic_governance_evidence_live_proof_readiness_check,
    minimal_governance_evidence_live_proof_readiness_environ,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

__all__ = (
    "CHECKLIST_REL",
    "FIXTURES_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "ControlPlanePost164DeepenEvidence",
    "ControlPlanePost164DeepenResult",
    "ControlPlanePost164DeepenViolation",
    "control_plane_post164_deepen_contract_summary",
    "control_plane_post164_deepen_gate_closed",
    "evaluate_control_plane_post164_deepen",
    "hermetic_control_plane_post164_deepen_check",
    "minimal_control_plane_post164_deepen_environ",
    "run_post164_fixture_suite",
    "validate_checklist_document",
)

GATE_ID = "control-plane-post164-deepen"
PR_NUMBER = 165

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_control_plane_post164_deepen.py")
CHECKLIST_REL = Path("data/kilo_control_plane_post164_deepen/checklist.json")
FIXTURES_REL = Path("data/kilo_control_plane_post164_deepen/fixtures")


@dataclass(frozen=True)
class ControlPlanePost164DeepenViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ControlPlanePost164DeepenEvidence:
    gate_id: str
    pr_number: int
    governance_readiness_ok: bool
    envelope_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class ControlPlanePost164DeepenResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[ControlPlanePost164DeepenViolation]
    evidence: ControlPlanePost164DeepenEvidence | None = None


def minimal_control_plane_post164_deepen_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_governance_evidence_live_proof_readiness_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[ControlPlanePost164DeepenViolation]:
    violations: list[ControlPlanePost164DeepenViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(ControlPlanePost164DeepenViolation(code="gate_id", message="gate_id"))
    if doc.get("live_verified") is True:
        violations.append(ControlPlanePost164DeepenViolation(code="live_verified", message="false"))
    if doc.get("post164_deepen_label") != POST164_DEEPEN_LABEL:
        violations.append(ControlPlanePost164DeepenViolation(code="label", message="label"))
    prior = doc.get("prior_gate_ids") or []
    if PRIOR_GATE_ID not in prior:
        violations.append(ControlPlanePost164DeepenViolation(code="prior", message=PRIOR_GATE_ID))
    return violations


def run_post164_fixture_suite() -> tuple[int, int, list[str]]:
    errors: list[str] = []
    positive = 0
    negative = 0
    _, errs = validate_post164_request_envelope({"correlation_id": "cp-pr165-ok"})
    if not errs:
        positive += 1
    else:
        errors.append("valid_envelope")
    _, bad = validate_post164_request_envelope({"live_verified": True})
    if bad:
        negative += 1
    else:
        errors.append("live_verified_should_fail")
    resp_v = assert_hermetic_control_plane_response({"four_state_max": "LIVE_VERIFIED"})
    if resp_v:
        negative += 1
    else:
        errors.append("cap_should_fail")
    fixtures_dir = REPO_ROOT / FIXTURES_REL
    if fixtures_dir.is_dir():
        for path in sorted(fixtures_dir.glob("*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("expect_envelope_ok"):
                _, e = validate_post164_request_envelope(doc.get("body") or {})
                if e:
                    errors.append(f"{path.name}: envelope")
                else:
                    positive += 1
    return positive, negative, errors


def evaluate_control_plane_post164_deepen(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> ControlPlanePost164DeepenResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[ControlPlanePost164DeepenViolation] = []

    gov = hermetic_governance_evidence_live_proof_readiness_check(env)
    if not gov.ok:
        violations.append(ControlPlanePost164DeepenViolation(code="prior", message=PRIOR_GATE_ID))

    mod_blob = (REPO_ROOT / Path("thinkbox/control_plane_post164_deepen.py")).read_text(encoding="utf-8")
    if not post164_deepen_markers_present(mod_blob):
        violations.append(ControlPlanePost164DeepenViolation(code="markers", message="markers"))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(ControlPlanePost164DeepenViolation(code="checklist", message="missing"))

    pos, neg, fixture_errors = run_post164_fixture_suite()
    for err in fixture_errors:
        violations.append(ControlPlanePost164DeepenViolation(code="fixture", message=err))

    envelope_ok = pos >= 1 and neg >= 1
    ok = gov.ok and envelope_ok and not fixture_errors and len(violations) == 0
    evidence = ControlPlanePost164DeepenEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        governance_readiness_ok=gov.ok,
        envelope_ok=envelope_ok,
    )
    return ControlPlanePost164DeepenResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_control_plane_post164_deepen_check(
    environ: Mapping[str, str] | None = None,
) -> ControlPlanePost164DeepenResult:
    env = environ if environ is not None else os.environ
    return evaluate_control_plane_post164_deepen(detect_matrix_mode(env), env)


def control_plane_post164_deepen_gate_closed() -> bool:
    return hermetic_control_plane_post164_deepen_check(
        minimal_control_plane_post164_deepen_environ(),
    ).ok


def control_plane_post164_deepen_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_control_plane_post164_deepen_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr165_theme_b_gate_id": GATE_ID,
        "post164_deepen_label": POST164_DEEPEN_LABEL,
        "post164_deepen_version": POST164_DEEPEN_VERSION,
        "prior_gate_id": PRIOR_GATE_ID,
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": control_plane_post164_deepen_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "contract_snippet": control_plane_post164_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
