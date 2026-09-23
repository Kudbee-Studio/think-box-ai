"""Hermetic swarm / governance post-#165 deepen gate (PR #166 theme D)."""

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
from thinkbox.kilo_pr165_combined_harden_era_chronicle import (
    GATE_ID as PR165_GATE_ID,
    hermetic_pr165_combined_harden_era_chronicle_check,
)
from thinkbox.kilo_pr165_combined_harden_era_chronicle import (
    minimal_pr165_combined_environ,
)
from thinkbox.kilo_swarm_instrumentation import (
    GATE_ID as SWARM_GATE,
    hermetic_swarm_operator_check,
    swarm_instrumentation_contract_summary,
)
from thinkbox.swarm_governance_post165_deepen import (
    SWARM_GOV_POST165_LABEL,
    SWARM_GOV_POST165_VERSION,
    admission_evidence_shape_ok,
    swarm_governance_post165_contract_snippet,
)

__all__ = (
    "CHECKLIST_REL",
    "GATE_ID",
    "PR_NUMBER",
    "VERIFY_SCRIPT_REL",
    "SwarmGovPost165Evidence",
    "SwarmGovPost165Result",
    "SwarmGovPost165Violation",
    "evaluate_swarm_governance_post165_deepen",
    "hermetic_swarm_governance_post165_deepen_check",
    "minimal_swarm_governance_post165_deepen_environ",
    "swarm_governance_post165_deepen_contract_summary",
    "swarm_governance_post165_deepen_gate_closed",
    "validate_checklist_document",
)

GATE_ID = "swarm-governance-post165-deepen"
PR_NUMBER = 166

VERIFY_SCRIPT_REL = Path("scripts/verify_kilo_swarm_governance_post165_deepen.py")
CHECKLIST_REL = Path("data/kilo_swarm_governance_post165_deepen/checklist.json")


@dataclass(frozen=True)
class SwarmGovPost165Violation:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class SwarmGovPost165Evidence:
    gate_id: str
    pr_number: int
    swarm_ok: bool
    governance_ok: bool
    governance_readiness_ok: bool
    pr165_ok: bool
    shape_ok: bool
    live_api_called: bool = False
    four_state_max: str = "TEST_VERIFIED"


@dataclass(frozen=True)
class SwarmGovPost165Result:
    mode: EnvMatrixMode
    ok: bool
    violations: list[SwarmGovPost165Violation]
    evidence: SwarmGovPost165Evidence | None = None


def minimal_swarm_governance_post165_deepen_environ(
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base: MutableMapping[str, str] = dict(minimal_pr165_combined_environ())
    base.update(minimal_governance_hermetic_environ())
    if extra:
        base.update(extra)
    return dict(base)


def validate_checklist_document(doc: Mapping[str, Any]) -> list[SwarmGovPost165Violation]:
    violations: list[SwarmGovPost165Violation] = []
    if doc.get("gate_id") != GATE_ID:
        violations.append(SwarmGovPost165Violation(code="gate_id", message="gate_id"))
    if doc.get("live_verified") is True:
        violations.append(SwarmGovPost165Violation(code="live_verified", message="false"))
    prior = doc.get("prior_gate_ids") or []
    for required in (SWARM_GATE, GOV_EVIDENCE_GATE, GOV_READINESS_GATE, PR165_GATE_ID):
        if required not in prior:
            violations.append(SwarmGovPost165Violation(code="prior_missing", message=required))
    return violations


def evaluate_swarm_governance_post165_deepen(
    mode: EnvMatrixMode | None = None,
    environ: Mapping[str, str] | None = None,
) -> SwarmGovPost165Result:
    env = environ if environ is not None else os.environ
    resolved = mode if mode is not None else detect_matrix_mode(env)
    violations: list[SwarmGovPost165Violation] = []

    swarm = hermetic_swarm_operator_check(env)
    if not swarm.ok:
        violations.append(SwarmGovPost165Violation(code="swarm", message=SWARM_GATE))
    gov = hermetic_governance_operator_check(env)
    if not gov.ok:
        violations.append(SwarmGovPost165Violation(code="governance", message=GOV_EVIDENCE_GATE))
    gov_ready = hermetic_governance_evidence_live_proof_readiness_check(env)
    if not gov_ready.ok:
        violations.append(SwarmGovPost165Violation(code="gov_readiness", message=GOV_READINESS_GATE))
    pr165 = hermetic_pr165_combined_harden_era_chronicle_check(env)
    if not pr165.ok:
        violations.append(SwarmGovPost165Violation(code="pr165", message=PR165_GATE_ID))

    checklist = REPO_ROOT / CHECKLIST_REL
    if checklist.is_file():
        violations.extend(validate_checklist_document(json.loads(checklist.read_text())))
    else:
        violations.append(SwarmGovPost165Violation(code="checklist_missing", message=""))

    summaries = (
        swarm_instrumentation_contract_summary(env),
        governance_evidence_contract_summary(env),
        governance_evidence_live_proof_readiness_contract_summary(env),
    )
    shape_ok = all(admission_evidence_shape_ok(s) for s in summaries)
    if not shape_ok:
        violations.append(SwarmGovPost165Violation(code="shape", message="admission_evidence"))

    ok = swarm.ok and gov.ok and gov_ready.ok and pr165.ok and shape_ok and len(violations) == 0
    evidence = SwarmGovPost165Evidence(
        gate_id=GATE_ID,
        pr_number=PR_NUMBER,
        swarm_ok=swarm.ok,
        governance_ok=gov.ok,
        governance_readiness_ok=gov_ready.ok,
        pr165_ok=pr165.ok,
        shape_ok=shape_ok,
    )
    return SwarmGovPost165Result(
        mode=resolved,
        ok=ok,
        violations=violations if not ok else [],
        evidence=evidence,
    )


def hermetic_swarm_governance_post165_deepen_check(
    environ: Mapping[str, str] | None = None,
) -> SwarmGovPost165Result:
    env = environ if environ is not None else os.environ
    return evaluate_swarm_governance_post165_deepen(detect_matrix_mode(env), env)


def swarm_governance_post165_deepen_gate_closed() -> bool:
    return hermetic_swarm_governance_post165_deepen_check(
        minimal_swarm_governance_post165_deepen_environ(),
    ).ok


def swarm_governance_post165_deepen_contract_summary(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    result = hermetic_swarm_governance_post165_deepen_check(env)
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "pr166_theme_d_gate_id": GATE_ID,
        "swarm_gov_label": SWARM_GOV_POST165_LABEL,
        "swarm_gov_version": SWARM_GOV_POST165_VERSION,
        "prior_gate_ids": [SWARM_GATE, GOV_EVIDENCE_GATE, GOV_READINESS_GATE, PR165_GATE_ID],
        "detected_mode": detect_matrix_mode(env).value,
        "hermetic_operator_ok": result.ok,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "gate_closed_default": swarm_governance_post165_deepen_gate_closed(),
        "verify_script": str(VERIFY_SCRIPT_REL),
        "contract_snippet": swarm_governance_post165_contract_snippet(),
        "hermetic_violation_codes": sorted({v.code for v in result.violations}),
    }
