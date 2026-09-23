"""Umbrella gate: PR #166 combined post-#165 lane (themes A–D)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_api_ops_harden_post165 import (
    GATE_ID as THEME_B_GATE_ID,
    api_ops_harden_post165_contract_summary,
    hermetic_api_ops_harden_post165_check,
    minimal_api_ops_harden_post165_environ,
)
from thinkbox.kilo_dashboard_pr165_gates_bind import (
    GATE_ID as THEME_C_GATE_ID,
    dashboard_pr165_gates_bind_contract_summary,
    hermetic_dashboard_pr165_gates_bind_check,
)
from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_live_proof_operator_prep_deepen import (
    GATE_ID as THEME_A_GATE_ID,
    hermetic_live_proof_operator_prep_deepen_check,
    live_proof_operator_prep_deepen_contract_summary,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_pr165_combined_harden_era_chronicle import GATE_ID as PRIOR_GATE_ID
from thinkbox.kilo_swarm_governance_post165_deepen import (
    GATE_ID as THEME_D_GATE_ID,
    hermetic_swarm_governance_post165_deepen_check,
    swarm_governance_post165_deepen_contract_summary,
)

__all__ = (
    "CHECKLIST_REL",
    "GATE_ID",
    "PR166_PASS_REL",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "Pr166CombinedEvidence",
    "Pr166CombinedResult",
    "Pr166CombinedViolation",
    "evaluate_pr166_combined_post165_lane",
    "hermetic_pr166_combined_post165_lane_check",
    "minimal_pr166_combined_environ",
    "pr166_combined_post165_lane_contract_summary",
    "pr166_combined_post165_lane_gate_closed",
    "validate_checklist_document",
)

GATE_ID = "pr166-combined-post165-lane"
PR_NUMBER = 166

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_pr166_combined_post165_lane.py")
CHECKLIST_REL = Path("data/kilo_pr166_combined_post165_lane/checklist.json")
PR166_PASS_REL = Path("docs/audit/passes/2026-09-23-pr166.json")


@dataclass(frozen=True)
class Pr166CombinedViolation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class Pr166CombinedEvidence:
    gate_id: str
    pr_number: int
    theme_a_ok: bool
    theme_b_ok: bool
    theme_c_ok: bool
    theme_d_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class Pr166CombinedResult:
    mode: EnvMatrixMode
    ok: bool
    violations: list[Pr166CombinedViolation]
    evidence: Pr166CombinedEvidence | None = None


def minimal_pr166_combined_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_api_ops_harden_post165_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[Pr166CombinedViolation]:
    violations: list[Pr166CombinedViolation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(Pr166CombinedViolation(code="gate_id", message="gate_id"))
    if doc.get("pr_number") != PR_NUMBER:
        violations.append(Pr166CombinedViolation(code="pr_number", message="pr_number"))
    if doc.get("live_verified") is True:
        violations.append(Pr166CombinedViolation(code="live_verified", message="false"))
    if doc.get("live_api_called") is True:
        violations.append(Pr166CombinedViolation(code="live_api", message="false"))
    prior = doc.get("prior_gate_ids") or []
    for required in (
        PRIOR_GATE_ID,
        THEME_A_GATE_ID,
        THEME_B_GATE_ID,
        THEME_C_GATE_ID,
        THEME_D_GATE_ID,
    ):
        if required not in prior:
            violations.append(Pr166CombinedViolation(code="prior_missing", message=required))
    return violations


def evaluate_pr166_combined_post165_lane(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> Pr166CombinedResult:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[Pr166CombinedViolation] = []

    theme_a = hermetic_live_proof_operator_prep_deepen_check(env)
    if not theme_a.ok:
        violations.append(Pr166CombinedViolation(code="theme_a", message=THEME_A_GATE_ID))
    theme_b = hermetic_api_ops_harden_post165_check(env)
    if not theme_b.ok:
        violations.append(Pr166CombinedViolation(code="theme_b", message=THEME_B_GATE_ID))
    theme_c = hermetic_dashboard_pr165_gates_bind_check(env)
    if not theme_c.ok:
        violations.append(Pr166CombinedViolation(code="theme_c", message=THEME_C_GATE_ID))
    theme_d = hermetic_swarm_governance_post165_deepen_check(env)
    if not theme_d.ok:
        violations.append(Pr166CombinedViolation(code="theme_d", message=THEME_D_GATE_ID))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(Pr166CombinedViolation(code="checklist", message="missing"))

    audit = REPO_ROOT / PR166_PASS_REL
    if audit.is_file():
        body = json.loads(audit.read_text(encoding="utf-8"))
        if body.get("live_verified") is True or body.get("live_api_called") is True:
            violations.append(Pr166CombinedViolation(code="audit_honesty", message="audit pass"))
    else:
        violations.append(Pr166CombinedViolation(code="audit_pass_missing", message=str(PR166_PASS_REL)))

    ok = theme_a.ok and theme_b.ok and theme_c.ok and theme_d.ok and len(violations) == 0
    evidence = Pr166CombinedEvidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        theme_a_ok=theme_a.ok,
        theme_b_ok=theme_b.ok,
        theme_c_ok=theme_c.ok,
        theme_d_ok=theme_d.ok,
    )
    return Pr166CombinedResult(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_pr166_combined_post165_lane_check(
    environ: Mapping[str, str] | None = None,
) -> Pr166CombinedResult:
    env = environ if environ is not None else os.environ
    return evaluate_pr166_combined_post165_lane(detect_matrix_mode(env), env)


def pr166_combined_post165_lane_gate_closed() -> bool:
    return hermetic_pr166_combined_post165_lane_check(minimal_pr166_combined_environ()).ok


def pr166_combined_post165_lane_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_pr166_combined_post165_lane_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr166_gate_id": GATE_ID,
        "prior_gate_id": PRIOR_GATE_ID,
        "theme_a": live_proof_operator_prep_deepen_contract_summary(env),
        "theme_b": api_ops_harden_post165_contract_summary(env),
        "theme_c": dashboard_pr165_gates_bind_contract_summary(env),
        "theme_d": swarm_governance_post165_deepen_contract_summary(env),
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "live_proof_in_this_pr": False,
        "gate_closed_default": pr166_combined_post165_lane_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "audit_pass": str(PR166_PASS_REL),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
