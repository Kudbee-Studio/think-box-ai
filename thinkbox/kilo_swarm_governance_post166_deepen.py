"""Hermetic swarm / governance post-#166 deepen gate (PR #167 theme D)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from thinkbox.kilo_env_matrix import EnvMatrixMode, detect_matrix_mode
from thinkbox.kilo_governance_evidence import (
    GATE_ID as GOV_EVIDENCE_GATE,
    governance_evidence_contract_summary,
    hermetic_governance_operator_check,
    minimal_governance_hermetic_environ,
)
from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    GATE_ID as GOV_READINESS_GATE,
    governance_evidence_live_proof_readiness_contract_summary,
    hermetic_governance_evidence_live_proof_readiness_check,
)
from thinkbox.kilo_live_proof_readiness import REPO_ROOT
from thinkbox.kilo_pr166_combined_post165_lane import (
    GATE_ID as PR166_GATE_ID,
    hermetic_pr166_combined_post165_lane_check,
)
from thinkbox.kilo_swarm_governance_post165_deepen import (
    GATE_ID as POST165_SWARM_GATE,
    hermetic_swarm_governance_post165_deepen_check,
    minimal_swarm_governance_post165_deepen_environ,
)
from thinkbox.kilo_swarm_instrumentation import (
    GATE_ID as SWARM_GATE,
    hermetic_swarm_operator_check,
    swarm_instrumentation_contract_summary,
)
from thinkbox.swarm_governance_post166_deepen import (
    SWARM_GOV_POST166_LABEL,
    SWARM_GOV_POST166_VERSION,
    admission_evidence_shape_ok,
    swarm_governance_post166_contract_snippet,
)

__all__ = (
    "CHECKLIST_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "SwarmGovPost166Evidence",
    "SwarmGovPost166Result",
    "SwarmGovPost166Violation",
    "evaluate_swarm_governance_post166_deepen",
    "hermetic_swarm_governance_post166_deepen_check",
    "minimal_swarm_governance_post166_deepen_environ",
    "swarm_governance_post166_deepen_contract_summary",
    "swarm_governance_post166_deepen_gate_closed",
    "validate_checklist_document",
)

GATE_ID = "swarm-governance-post166-deepen"
PR_NUMBER = 167

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_swarm_governance_post166_deepen.py")
CHECKLIST_REL = Path("data/kilo_swarm_governance_post166_deepen/checklist.json")


@dataclass(frozen=True)
class SwarmGovPost166Violation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class SwarmGovPost166Evidence:
    gate_id: str
    pr_number: int
    swarm_ok: bool
    governance_ok: bool
    governance_readiness_ok: bool
    post165_swarm_ok: bool
    pr166_ok: bool
    shape_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class SwarmGovPost166Result:
    mode: EnvMatrixMode
    ok: bool
    violations: list[SwarmGovPost166Violation]
    evidence: SwarmGovPost166Evidence | None = None


def minimal_swarm_governance_post166_deepen_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_swarm_governance_post165_deepen_environ())
    base.update(minimal_governance_hermetic_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[SwarmGovPost166Violation]:
    violations: list[SwarmGovPost166Violation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(SwarmGovPost166Violation(code="gate_id", message="gate_id"))
    if doc.get("live_verified") is True:
        violations.append(SwarmGovPost166Violation(code="live_verified", message="false"))
    prior = doc.get("prior_gate_ids") or []
    for required in (
        SWARM_GATE,
        GOV_EVIDENCE_GATE,
        GOV_READINESS_GATE,
        POST165_SWARM_GATE,
        PR166_GATE_ID,
    ):
        if required not in prior:
            violations.append(SwarmGovPost166Violation(code="prior_missing", message=required))
    return violations


def evaluate_swarm_governance_post166_deepen(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> SwarmGovPost166Result:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[SwarmGovPost166Violation] = []

    swarm = hermetic_swarm_operator_check(env)
    if not swarm.ok:
        violations.append(SwarmGovPost166Violation(code="swarm", message=SWARM_GATE))
    gov = hermetic_governance_operator_check(env)
    if not gov.ok:
        violations.append(SwarmGovPost166Violation(code="governance", message=GOV_EVIDENCE_GATE))
    gov_ready = hermetic_governance_evidence_live_proof_readiness_check(env)
    if not gov_ready.ok:
        violations.append(SwarmGovPost166Violation(code="gov_readiness", message=GOV_READINESS_GATE))
    post165 = hermetic_swarm_governance_post165_deepen_check(env)
    if not post165.ok:
        violations.append(SwarmGovPost166Violation(code="post165_swarm", message=POST165_SWARM_GATE))
    pr166 = hermetic_pr166_combined_post165_lane_check(env)
    if not pr166.ok:
        violations.append(SwarmGovPost166Violation(code="pr166", message=PR166_GATE_ID))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(SwarmGovPost166Violation(code="checklist_missing", message=""))

    summaries = (
        swarm_instrumentation_contract_summary(env),
        governance_evidence_contract_summary(env),
        governance_evidence_live_proof_readiness_contract_summary(env),
    )
    shape_ok = all(admission_evidence_shape_ok(s) for s in summaries)
    if not shape_ok:
        violations.append(SwarmGovPost166Violation(code="shape", message="admission_evidence"))

    ok = (
        swarm.ok
        and gov.ok
        and gov_ready.ok
        and post165.ok
        and pr166.ok
        and shape_ok
        and len(violations) == 0
    )
    evidence = SwarmGovPost166Evidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        swarm_ok=swarm.ok,
        governance_ok=gov.ok,
        governance_readiness_ok=gov_ready.ok,
        post165_swarm_ok=post165.ok,
        pr166_ok=pr166.ok,
        shape_ok=shape_ok,
    )
    return SwarmGovPost166Result(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_swarm_governance_post166_deepen_check(
    environ: Mapping[str, str] | None = None,
) -> SwarmGovPost166Result:
    env = environ if environ is not None else os.environ
    return evaluate_swarm_governance_post166_deepen(detect_matrix_mode(env), env)


def swarm_governance_post166_deepen_gate_closed() -> bool:
    return hermetic_swarm_governance_post166_deepen_check(
        minimal_swarm_governance_post166_deepen_environ(),
    ).ok


def swarm_governance_post166_deepen_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_swarm_governance_post166_deepen_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr167_theme_d_gate_id": GATE_ID,
        "swarm_gov_label": SWARM_GOV_POST166_LABEL,
        "swarm_gov_version": SWARM_GOV_POST166_VERSION,
        "prior_gate_ids": [
            SWARM_GATE,
            GOV_EVIDENCE_GATE,
            GOV_READINESS_GATE,
            POST165_SWARM_GATE,
            PR166_GATE_ID,
        ],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": swarm_governance_post166_deepen_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "contract_snippet": swarm_governance_post166_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
