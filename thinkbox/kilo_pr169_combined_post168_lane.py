"""Umbrella gate: PR #169 combined post-#168 lane (themes A–D)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_api_ops_harden_post168 import (
    GATE_ID as THEME_B_GATE_ID,
    hermetic_api_ops_harden_post168_check,
    minimal_api_ops_harden_post168_environ,
)
from thinkbox.kilo_dashboard_pr168_gates_bind import (
    GATE_ID as THEME_C_GATE_ID,
    hermetic_dashboard_pr168_gates_bind_check,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_hermetic_gate_memo import memoized_hermetic_check
from thinkbox.kilo_live_proof_operator_audit_flip_post168 import (
    GATE_ID as THEME_A_GATE_ID,
    hermetic_live_proof_operator_audit_flip_post168_check,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_pr168_combined_post167_lane import (
    GATE_ID as PRIOR_GATE_ID,
    PR168_PASS_REL as PRIOR_PR168_PASS_REL,
)
from thinkbox.kilo_swarm_governance_post168_deepen import (
    GATE_ID as THEME_D_GATE_ID,
    hermetic_swarm_governance_post168_deepen_check,
)

__all__ = (
    "CHECKLIST_REL",
    "GATE_ID",
    "PR169_PASS_REL",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "Pr169CombinedEvidence",
    "Pr169CombinedResult",
    "Pr169CombinedViolation",
    "evaluate_pr169_combined_post168_lane",
    "hermetic_pr169_combined_post168_lane_check",
    "minimal_pr169_combined_environ",
    "pr169_combined_post168_lane_contract_summary",
    "pr169_combined_post168_lane_gate_closed",
    "validate_checklist_document",
)

GATE_ID = "pr169-combined-post168-lane"
PR_NUMBER = 169

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_pr169_combined_post168_lane.py")
CHECKLIST_REL = Path("data/kilo_pr169_combined_post168_lane/checklist.json")
PR169_PASS_REL = Path("docs/audit/passes/2026-09-23-pr169.json")


@dataclass(frozen=True)
class Pr169CombinedViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class Pr169CombinedEvidence:
    gate_id: str
    pr_number: int
    theme_a_ok: bool
    theme_b_ok: bool
    theme_c_ok: bool
    theme_d_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class Pr169CombinedResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[Pr169CombinedViolation]
    evidence: Pr169CombinedEvidence | None = None


def minimal_pr169_combined_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_api_ops_harden_post168_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[Pr169CombinedViolation]:
    violations: list[Pr169CombinedViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(Pr169CombinedViolation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(Pr169CombinedViolation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(Pr169CombinedViolation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(Pr169CombinedViolation(code="live_api", message="false"))
    prior = doc.get("prior_gate_ids") or []
    for required in (
        PRIOR_GATE_ID,
        THEME_A_GATE_ID,
        THEME_B_GATE_ID,
        THEME_C_GATE_ID,
        THEME_D_GATE_ID,
    ):
        if required not in prior:
            violations.append(Pr169CombinedViolation(code="prior_missing", message=required))
    return violations


def evaluate_pr169_combined_post168_lane(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> Pr169CombinedResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[Pr169CombinedViolation] = []

    theme_a = hermetic_live_proof_operator_audit_flip_post168_check(env)
    if not theme_a.ok:
        violations.append(Pr169CombinedViolation(code="theme_a", message=THEME_A_GATE_ID))
    theme_b = hermetic_api_ops_harden_post168_check(env)
    if not theme_b.ok:
        violations.append(Pr169CombinedViolation(code="theme_b", message=THEME_B_GATE_ID))
    theme_c = hermetic_dashboard_pr168_gates_bind_check(env)
    if not theme_c.ok:
        violations.append(Pr169CombinedViolation(code="theme_c", message=THEME_C_GATE_ID))
    theme_d = hermetic_swarm_governance_post168_deepen_check(env)
    if not theme_d.ok:
        violations.append(Pr169CombinedViolation(code="theme_d", message=THEME_D_GATE_ID))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(Pr169CombinedViolation(code="checklist", message="missing"))

    audit = REPO_ROOT / PR169_PASS_REL
    if audit.is_file():
        body = json.loads(audit.read_text(encoding="utf-8"))
        if body.get("live_verified") is True or body.get("live_api_called") is True:
            violations.append(Pr169CombinedViolation(code="audit_honesty", message="audit pass"))
    else:
        violations.append(Pr169CombinedViolation(code="audit_pass_missing", message=str(PR169_PASS_REL)))

    prior_audit = REPO_ROOT / PRIOR_PR168_PASS_REL
    if not prior_audit.is_file():
        violations.append(
            Pr169CombinedViolation(code="prior_audit_missing", message=str(PRIOR_PR168_PASS_REL)),
        )
    else:
        prior_body = json.loads(prior_audit.read_text(encoding="utf-8"))
        if prior_body.get("gate_id") != PRIOR_GATE_ID:
            violations.append(Pr169CombinedViolation(code="prior_audit_gate", message=PRIOR_GATE_ID))
        if prior_body.get("live_verified") is True or prior_body.get("live_api_called") is True:
            violations.append(Pr169CombinedViolation(code="prior_audit_honesty", message="pr168 pass"))

    ok = theme_a.ok and theme_b.ok and theme_c.ok and theme_d.ok and len(violations) == 0
    evidence = Pr169CombinedEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        theme_a_ok=theme_a.ok,
        theme_b_ok=theme_b.ok,
        theme_c_ok=theme_c.ok,
        theme_d_ok=theme_d.ok,
    )
    return Pr169CombinedResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_pr169_combined_post168_lane_check(
    environ: Mapping[str, str] | None = None,
) -> Pr169CombinedResult:
    env = environ if environ is not None else os.environ
    return memoized_hermetic_check(
        GATE_ID,
        env,
        lambda: evaluate_pr169_combined_post168_lane(detect_matrix_mode(env), env),
    )


def pr169_combined_post168_lane_gate_closed() -> bool:
    return hermetic_pr169_combined_post168_lane_check(minimal_pr169_combined_environ()).ok


def _theme_lane_summary(gate_id: str, *, hermetic_ok: bool) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "hermetic_operator_ok": hermetic_ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }


def pr169_combined_post168_lane_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_pr169_combined_post168_lane_check(env)
    evidence = result.evidence
    theme_a_ok = evidence.theme_a_ok if evidence else False
    theme_b_ok = evidence.theme_b_ok if evidence else False
    theme_c_ok = evidence.theme_c_ok if evidence else False
    theme_d_ok = evidence.theme_d_ok if evidence else False
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr169_gate_id": GATE_ID,
        "prior_gate_id": PRIOR_GATE_ID,
        "theme_a": _theme_lane_summary(THEME_A_GATE_ID, hermetic_ok=theme_a_ok),
        "theme_b": _theme_lane_summary(THEME_B_GATE_ID, hermetic_ok=theme_b_ok),
        "theme_c": _theme_lane_summary(THEME_C_GATE_ID, hermetic_ok=theme_c_ok),
        "theme_d": _theme_lane_summary(THEME_D_GATE_ID, hermetic_ok=theme_d_ok),
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": result.ok,
        "verify_script": str(VERIFY_SCRIPT_REL),
        "audit_pass": str(PR169_PASS_REL),
        "prior_audit_pass": str(PRIOR_PR168_PASS_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
